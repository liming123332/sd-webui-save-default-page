import gradio as gr
import gc

from modules import script_callbacks, sd_models
from modules.ui_components import ToolButton
from modules.ui import save_style_symbol, refresh_symbol


_buttons = {}


def unload_models_from_memory():
    """
    从缓存和内存中卸载所有模型
    Unload all models from cache and memory
    """
    try:
        print("开始卸载模型...")

        # 使用 WebUI 的安全卸载方法
        result_msg = sd_models.unload_model_weights()

        # 清理垃圾回收
        gc.collect()

        # 尝试清理 GPU 内存（如果可用）
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        result = f"✅ 模型卸载成功: {result_msg}"
        print(result)
        return result

    except Exception as e:
        error_msg = f"❌ 卸载模型时出错: {str(e)}"
        print(error_msg)
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