import gradio as gr
import gc

from modules import script_callbacks, sd_models, shared, devices
from modules.ui_components import ToolButton
from modules.ui import save_style_symbol, refresh_symbol


_buttons = {}


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
        print("开始安全卸载模型...")

        # 1. 卸载当前模型权重
        result_msg = sd_models.unload_model_weights()

        # 2. 安全重置模型状态 - 避免破坏系统
        try:
            if hasattr(shared, 'sd_model') and shared.sd_model is not None:
                shared.sd_model = None
        except Exception:
            pass

        try:
            if hasattr(sd_models, 'model_data'):
                sd_models.model_data.sd_model = None
                sd_models.model_data.loaded_sd_models = []
                sd_models.model_data.was_loaded_at_least_once = False
        except Exception:
            pass

        # 3. 安全清理额外网络（不重置注册表）
        try:
            _clear_lora_networks()
        except Exception:
            pass

        # 4. 安全清理 VAE 模型
        try:
            if hasattr(shared, 'sd_vae'):
                shared.sd_vae = None
        except Exception:
            pass

        # 5. 清理 GPU 缓存
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
        except Exception:
            pass

        # 6. 安全的内存清理
        try:
            gc.collect()
        except Exception:
            pass

        result = f"✅ 模型安全卸载成功: {result_msg}"
        print(result)
        return result

    except Exception as e:
        error_msg = f"❌ 卸载模型时出错: {str(e)}"
        print(error_msg)

        # 基本的状态重置
        try:
            if hasattr(shared, 'sd_model'):
                shared.sd_model = None
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