import gradio as gr

from modules import script_callbacks
from modules.ui_components import ToolButton
from modules.ui import save_style_symbol


_buttons = {}


def _inject_save_defaults_button(component, **kwargs):
    elem_id = getattr(component, 'elem_id', None)
    if elem_id in ("txt2img_tools", "img2img_tools"):
        with component:
            btn = ToolButton(value=save_style_symbol, elem_id=f"{elem_id}_save_defaults_ext", tooltip="保存当前页面为默认")
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
        _buttons[elem_id] = btn


script_callbacks.on_after_component(_inject_save_defaults_button, name="save-defaults-button-inject")