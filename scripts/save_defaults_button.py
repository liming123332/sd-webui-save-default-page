import gc
import json
import os

import gradio as gr

from modules import script_callbacks, sd_models, shared, devices
from modules.ui_components import ToolButton
from modules.ui import save_style_symbol, refresh_symbol


# ponytail: 通用字段 —— (preset 后缀, txt2img elem_id, img2img elem_id)
# 这些控件被 Forge 标记 _internal_preset_param,不归 ui-config.json 管,
# 真正默认值在 shared.opts.{arch}_{t2i|i2i}_{suffix}。见 modules_forge/presets.py
# 与 modules_forge/main_entry.py:on_preset_change 的读取侧。
_COMMON = [
    ("sampler",   "txt2img_sampling",   "img2img_sampling"),
    ("scheduler", "txt2img_scheduler",  "img2img_scheduler"),
    ("step",      "txt2img_steps",      "img2img_steps"),
    ("width",     "txt2img_width",      "img2img_width"),
    ("height",    "txt2img_height",     "img2img_height"),
    ("cfg",       "txt2img_cfg_scale",  "img2img_cfg_scale"),
    # Distilled CFG(anima 下显示为 "Shift",复用同一控件/key)
    ("dcfg",      "txt2img_distilled_cfg_scale", "img2img_distilled_cfg_scale"),
]
# ponytail: Hires.fix preset 参数(同样被 _internal_preset_param 标记),仅 txt2img。
# key = {arch}_t2i_{suffix} —— on_preset_change:303/317/321 读取
_HIRES = [
    ("hr_step", "txt2img_hires_steps"),
    ("hr_cfg",  "txt2img_hr_cfg"),
    ("hr_dcfg", "txt2img_hr_distilled_cfg"),
]
# ponytail: 字段映射自检 —— suffix 必须与 on_preset_change 读取的 key 一致
assert {s for s, _, _ in _COMMON} == {"sampler", "scheduler", "step", "width", "height", "cfg", "dcfg"}
assert {f"t2i_{s}" for s, _ in _HIRES} == {"t2i_hr_step", "t2i_hr_cfg", "t2i_hr_dcfg"}

# ponytail: Hires VAE/TE 是 multiselect,清空([])时 ui_apply 会跳过(ui_loadsave.py:196 的 new_value==[]),
# 仅 txt2img 有,需插件直接补写 ui-config.json。elem_id 来自 ui.py:287。
_HR_VAE_ELEM = "hr_vae_te"
_HR_VAE_KEY = "txt2img/Hires VAE / Text Encoder/value"
_T2I_ELEMS = tuple(c[1] for c in _COMMON) + tuple(h[1] for h in _HIRES) + (_HR_VAE_ELEM,)
_I2I_ELEMS = tuple(c[2] for c in _COMMON)
assert _HR_VAE_ELEM in _T2I_ELEMS, "hr_vae_te 未在 t2i inputs,清空补写不会触发"
# tab -> (tools elem_id, 目标 elem_ids, preset 后缀)
_TABS = {
    "txt2img": ("txt2img_tools", _T2I_ELEMS, "t2i"),
    "img2img": ("img2img_tools", _I2I_ELEMS, "i2i"),
}

_buttons = {}   # tab -> (save_btn, out_html)
_comps = {}     # elem_id -> gradio component
_bound = set()  # 已绑定 click 的 tab


# 触发 Forge 自带 ui_defaults_apply,把所有普通参数(hr_upscaler/denoising/... 等)写进 ui-config.json,
# 再 reload UI 让 ui-config 与 preset 都生效。去掉了无效的 ui_defaults_save 和会与 fn 竞争 config.json 的 settings_submit。
_APPLY_JS = """
function(){
    const app = gradioApp();
    const clickTabByText = (container, text) => {
        if(!container) return false;
        const tabs = container.querySelectorAll('[role=tab]');
        for (const t of tabs){ if((t.innerText||'').trim()===text){ t.click(); return true; } }
        return false;
    };
    const clickById = (id) => { const el = app.getElementById(id); if(el){ el.click(); return true; } return false; };
    const reload = () => {
        if(clickById('settings_restart_gradio') || clickById('settings_reload_ui')) return;
        const btns = app.querySelectorAll('[role=button],button');
        for(const b of btns){ const t=(b.innerText||'').trim(); if(['Reload UI','重载UI'].includes(t)){ b.click(); return; } }
    };
    clickTabByText(app.querySelector('#tabs'), 'Settings');
    setTimeout(()=>{
        clickTabByText(app.querySelector('#settings'), 'Defaults');
        setTimeout(()=>{
            clickById('ui_defaults_apply');          // 写 ui-config.json(所有普通参数,含 hires 的 hr_upscaler/denoising 等)
            setTimeout(reload, 800);                 // 等 ui_defaults_apply 后端 + fn 写 preset 都完成
        }, 200);
    }, 200);
}
"""


def _clear_lora_networks():
    """清理 LoRA 网络"""
    try:
        # 尝试访问 LoRA 扩展的 loaded_networks
        from modules import extra_networks

        # 创建空的处理对象来触发所有额外网络的 deactivate
        class DummyProcessing:
            pass

        p = DummyProcessing()

        # 清理所有额外网络
        extra_networks.deactivate(p, {})

        # 清理 LoRA 特定的网络
        try:
            import networks
            if hasattr(networks, 'loaded_networks'):
                networks.loaded_networks.clear()
            if hasattr(networks, 'networks_in_memory'):
                networks.networks_in_memory.clear()
            if hasattr(networks, 'loaded_bundle_embeddings'):
                networks.loaded_bundle_embeddings.clear()
        except ImportError:
            pass

        print("✅ LoRA 网络已清理")

    except Exception as e:
        print(f"⚠️ 清理 LoRA 网络时出现警告: {str(e)}")


def _clear_extra_networks():
    """清理所有额外网络（包括 LoRA, hypernetworks 等）"""
    try:
        from modules import extra_networks

        # 重置额外网络注册表
        extra_networks.initialize()

        # 清理所有已加载的额外网络
        class DummyProcessing:
            pass

        p = DummyProcessing()

        # 调用 deactivate 清理所有网络
        for name, extra_network in extra_networks.extra_network_registry.items():
            try:
                extra_network.deactivate(p)
            except Exception as e:
                print(f"⚠️ 清理额外网络 {name} 时出现警告: {str(e)}")

        print("✅ 额外网络已清理")

    except Exception as e:
        print(f"⚠️ 清理额外网络时出现警告: {str(e)}")


def unload_models_from_memory():
    """
    安全地卸载所有模型并重置状态，避免破坏系统模块
    Safely unload all models and reset state without breaking system modules
    """
    try:
        print("🔄 开始安全卸载模型...")
        unloaded_items = []

        # 1. 卸载当前主模型权重到 CPU
        current_model = None
        try:
            if hasattr(shared, 'sd_model') and shared.sd_model is not None:
                if hasattr(shared.sd_model, 'sd_checkpoint_info'):
                    current_model = shared.sd_model.sd_checkpoint_info.title
                elif hasattr(shared.sd_model, 'filename'):
                    current_model = shared.sd_model.filename
                else:
                    current_model = "当前主模型"

                result_msg = sd_models.unload_model_weights()
                unloaded_items.append(f"🎨 主模型: {current_model}")
            else:
                result_msg = "没有加载的主模型"
        except Exception as e:
            result_msg = f"卸载主模型时出错: {str(e)}"

        # 2. 清理 model_data 状态
        try:
            if hasattr(sd_models, 'model_data'):
                if hasattr(sd_models.model_data, 'loaded_sd_models') and sd_models.model_data.loaded_sd_models:
                    model_count = len(sd_models.model_data.loaded_sd_models)
                    sd_models.model_data.loaded_sd_models = []
                    unloaded_items.append(f"📋 已加载模型列表 ({model_count} 个)")

                sd_models.model_data.was_loaded_at_least_once = False
        except Exception:
            pass

        # 3. 清理 LoRA 和额外网络
        lora_count = 0
        try:
            import networks
            if hasattr(networks, 'loaded_networks'):
                lora_count = len(networks.loaded_networks)
                networks.loaded_networks.clear()
                networks.networks_in_memory.clear()
                networks.loaded_bundle_embeddings.clear()
                if lora_count > 0:
                    unloaded_items.append(f"🌟 LoRA 模型 ({lora_count} 个)")

            # 清理其他额外网络
            from modules import extra_networks
            class DummyProcessing:
                pass
            extra_networks.deactivate(DummyProcessing(), {})
            unloaded_items.append("🔗 其他额外网络")
        except ImportError:
            pass
        except Exception:
            pass

        # 4. 清理 VAE 模型
        try:
            vae_name = "未知 VAE"
            if hasattr(shared, 'sd_vae') and shared.sd_vae is not None:
                if hasattr(shared.sd_vae, 'filename'):
                    vae_name = shared.sd_vae.filename
                elif hasattr(shared.sd_vae, 'name'):
                    vae_name = shared.sd_vae.name
                shared.sd_vae = None
                unloaded_items.append(f"🎭 VAE 模型: {vae_name}")
        except Exception:
            pass

        # 5. 清理 Textual Inversion 嵌入
        embedding_count = 0
        try:
            if hasattr(shared, 'sd_embedding_db'):
                if hasattr(shared.sd_embedding_db, 'word_embeddings'):
                    embedding_count = len(shared.sd_embedding_db.word_embeddings)
                    shared.sd_embedding_db.word_embeddings.clear()
                if hasattr(shared.sd_embedding_db, 'loaded_embeddings'):
                    if embedding_count == 0:
                        embedding_count = len(shared.sd_embedding_db.loaded_embeddings)
                    shared.sd_embedding_db.loaded_embeddings.clear()
                if embedding_count > 0:
                    unloaded_items.append(f"📝 文本嵌入 ({embedding_count} 个)")
        except Exception:
            pass

        # 6. 清理 GPU 缓存
        try:
            import torch
            if torch.cuda.is_available():
                memory_before = torch.cuda.memory_allocated() / (1024**2)  # MB
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                memory_after = torch.cuda.memory_allocated() / (1024**2)  # MB
                freed_memory = memory_before - memory_after
                if freed_memory > 1:  # 只显示有意义的内存释放
                    unloaded_items.append(f"💾 GPU 缓存 (释放 {freed_memory:.1f} MB)")
        except Exception:
            pass

        # 7. 垃圾回收
        try:
            gc.collect()
            unloaded_items.append("🧹 系统垃圾回收")
        except Exception:
            pass

        # 构建详细结果
        if unloaded_items:
            details = "\n".join(f"  ✅ {item}" for item in unloaded_items)
            result = f"🎯 模型卸载完成！\n{details}\n\n📊 主模型状态: {result_msg}"
        else:
            result = "ℹ️ 没有发现需要卸载的模型"

        print(result)
        return result

    except Exception as e:
        error_msg = f"❌ 卸载模型时出错: {str(e)}"
        print(error_msg)
        return error_msg


def _patch_ui_config(key, value):
    """直接改 ui-config.json 单个 key,绕过 ui_apply 对空列表的跳过(ui_loadsave.py:196)。"""
    try:
        path = shared.cmd_opts.ui_config_file
        data = {}
        if os.path.isfile(path):
            with open(path, "r", encoding="utf8") as f:
                data = json.load(f)
        if data.get(key) != value:
            data[key] = value
            with open(path, "w", encoding="utf8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[save-defaults] patched ui-config: {key} = {value}")
    except Exception as e:
        print(f"[save-defaults] patch ui-config failed: {e}")


def _save(p, *values):
    """把当前页面的 preset 参数写入当前架构并持久化到 config.json。
    普通参数(hr_upscaler/denoising 等)由 .then 触发的 ui_defaults_apply 写 ui-config.json。
    reload 后两者都由各自机制套用。"""
    arch = shared.opts.forge_preset
    print(f"[save-defaults] _save tab={p} arch={arch} vals={values}")
    n = len(_COMMON)
    for (suffix, _, _), v in zip(_COMMON, values[:n]):
        shared.opts.set(f"{arch}_{p}_{suffix}", v)
    if p == "t2i":
        # Hires. fix 仅 txt2img
        for (suffix, _), v in zip(_HIRES, values[n:n + len(_HIRES)]):
            shared.opts.set(f"{arch}_t2i_{suffix}", v)
        # ponytail: Hires VAE/TE 清空([])时 ui_apply 会跳过空列表,这里先补写,
        # 让随后 ui_defaults_apply 读到 new==old([]) 即保持 [] 而不再回弹
        hr_vae = values[n + len(_HIRES)]
        if hr_vae == []:
            _patch_ui_config(_HR_VAE_KEY, [])
    shared.opts.save(shared.config_filename)
    print(f"[save-defaults] _save done, wrote config.json")
    tab = "txt2img" if p == "t2i" else "img2img"
    return f"✅ 已保存为 {arch.upper()} 架构默认值（{tab}），重载 UI 后生效"


def _maybe_bind(tab):
    # ponytail: tools(toprow)先于目标组件创建,所以 click 必须延迟到这里绑
    if tab in _bound or tab not in _buttons:
        return
    _, elems, p = _TABS[tab]
    if not all(e in _comps for e in elems):
        return
    _bound.add(tab)
    btn, out = _buttons[tab]
    comps = [_comps[e] for e in elems]
    print(f"[save-defaults] bind {tab} ({len(comps)} inputs): {[getattr(c,'elem_id',None) for c in comps]}")
    # ponytail: fn 写 preset 单独一个 click(无 _js,避免 _js 切 Settings tab 干扰 inputs 收集);
    # 成功后 .then 触发 ui_defaults_apply 写普通参数 + reload —— reload 一定在 preset 写入之后
    btn.click(fn=lambda *a, p=p: _save(p, *a), inputs=comps, outputs=[out]).then(fn=lambda: None, _js=_APPLY_JS)


def _inject_buttons(component, tab):
    with component:
        btn = ToolButton(value=save_style_symbol,
                         elem_id=f"{tab}_save_defaults_ext",
                         tooltip="保存当前页面参数为默认")
        unload_btn = ToolButton(value=refresh_symbol,
                                elem_id=f"{tab}_unload_models_ext",
                                tooltip="从缓存和内存中卸载所有模型")
        out = gr.HTML("", elem_id=f"{tab}_save_defaults_ext_out")
    unload_btn.click(fn=unload_models_from_memory, inputs=[], outputs=[])
    _buttons[tab] = (btn, out)


def _after_component(component, **kwargs):
    eid = getattr(component, "elem_id", None)

    for tab, (tools_id, elems, _) in _TABS.items():
        if eid == tools_id:
            _inject_buttons(component, tab)
        if eid in elems:
            _comps[eid] = component
            _maybe_bind(tab)


script_callbacks.on_after_component(_after_component, name="save-defaults-button-inject")
