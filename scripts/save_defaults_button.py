import gradio as gr
import gc

from modules import script_callbacks, sd_models, shared, devices
from modules.ui_components import ToolButton
from modules.ui import save_style_symbol, refresh_symbol


_buttons = {}


def unload_models_from_memory():
    """
    从缓存和内存中完全卸载所有模型并重置状态
    Completely unload all models from cache and memory and reset state
    """
    try:
        print("开始完全卸载模型...")

        # 1. 卸载当前模型权重
        result_msg = sd_models.unload_model_weights()

        # 2. 完全重置模型状态 - 关键修复
        if hasattr(shared, 'sd_model'):
            shared.sd_model = None

        if hasattr(sd_models, 'model_data'):
            sd_models.model_data.sd_model = None
            sd_models.model_data.loaded_sd_models = []
            sd_models.model_data.was_loaded_at_least_once = False

        # 3. 清理 forge 相关状态（如果存在）
        try:
            import modules_forge.ops as forge_ops
            if hasattr(forge_ops, 'clear_cache'):
                forge_ops.clear_cache()
        except ImportError:
            pass

        # 4. 清理 patcher 系统（如果存在）
        try:
            import ldm_patched.modules.model_management as model_management
            model_management.cleanup_models()
            model_management.soft_empty_cache(force=True)
        except ImportError:
            pass

        # 5. 确保设备状态正确
        try:
            import torch
            # 确保设备重置为默认状态
            devices.device = devices.get_optimal_device()

            # 清理 CUDA 缓存
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except ImportError:
            pass

        # 6. 强制垃圾回收
        gc.collect()

        result = f"✅ 模型完全卸载成功: {result_msg}"
        print(result)
        return result

    except Exception as e:
        error_msg = f"❌ 完全卸载模型时出错: {str(e)}"
        print(error_msg)
        # 即使出错，也要尝试重置状态
        try:
            if hasattr(shared, 'sd_model'):
                shared.sd_model = None
            if hasattr(sd_models, 'model_data'):
                sd_models.model_data.sd_model = None
        except:
            pass
        return error_msg


def _inject_save_defaults_button(component, **kwargs):
    elem_id = getattr(component, 'elem_id', None)
    if elem_id in ("txt2img_tools", "img2img_tools"):
        with component:
            # 现有的保存默认按钮
            btn = ToolButton(value=save_style_symbol, elem_id=f"{elem_id}_save_defaults_ext", tooltip="保存当前页面为默认")

            # 新增的卸载模型按钮
            unload_btn = ToolButton(
                value=refresh_symbol,
                elem_id=f"{elem_id}_unload_models_ext",
                tooltip="从缓存和内存中卸载所有模型"
            )
        btn.click(
            fn=lambda: None,
            _js=(
                "function(){"
                "  const app = gradioApp();"
                "  const clickTabByText = (container, text) =>  {"
                "    if(!container) return false;"
                "    const tabs = container.querySelectorAll('[role=tab]');"
                "    for (const t of tabs){ if((t.innerText||'').trim()===text){ t.click(); return true; } }"
                "    return false;"
                "  };"
                "  const clickById = (id) => { const el = app.getElementById(id); if(el){ el.click(); return true; } return false; };"
                "  const clickButtonByText = (texts, container=null) => {"
                "    const root = container || app;"
                "    const btns = root.querySelectorAll('[role=button],button');"
                "    for(const b of btns){ const t=(b.innerText||'').trim(); if(texts.includes(t)){ b.click(); return true; } }"
                "    return false;"
                "  };"
                "  clickTabByText(app.querySelector('#tabs'), 'Settings');"
                "  setTimeout(()=>{"
                "    clickTabByText(app.querySelector('#settings'), 'Defaults');"
                "    setTimeout(()=>{"
                "      clickById('ui_defaults_save');"
                "      setTimeout(()=>{"
                "        clickById('ui_defaults_apply');"
                "        setTimeout(()=>{"
                "          if(!clickById('settings_submit')){ clickButtonByText(['Apply settings','应用设置']); }"
                "          setTimeout(()=>{"
                "            if(clickById('settings_restart_gradio') || clickById('settings_reload_ui')){} else { clickButtonByText(['Reload UI','重载UI']); }"
                "          }, 120);"
                "        }, 120);"
                "      }, 120);"
                "    }, 120);"
                "  }, 120);"
                "}"
            ),
            inputs=[],
            outputs=[]
        )

        # 卸载模型按钮的点击事件
        unload_btn.click(
            fn=unload_models_from_memory,
            inputs=[],
            outputs=[]
        )

        _buttons[elem_id] = {
            'save_btn': btn,
            'unload_btn': unload_btn
        }


script_callbacks.on_after_component(_inject_save_defaults_button, name="save-defaults-button-inject")