# sd-webui-save-default-page

一个面向 Stable Diffusion WebUI（reForge/A1111 分支）的轻量扩展，向 `txt2img` 与 `img2img` 工具栏注入两个便捷按钮：

- 一键保存当前页面为默认（自动进入设置页 Defaults → 保存/应用 → 应用设置 → 重载 UI）
- 一键卸载模型并释放显存/内存（卸载权重、清理 LoRA/额外网络状态、VAE、CUDA 缓存等）

## 功能
- 保存默认页面：自动执行 Settings → Defaults 的保存与应用，并重载界面。
- 卸载模型缓存：安全卸载当前模型权重与相关缓存，尽量不影响系统模块状态。

## 安装
- 将本扩展文件夹放入 Stable Diffusion WebUI 的 `extensions` 目录，例如：
  - `stable-diffusion-webui/extensions/sd-webui-save-default-page`
- 重启或重载 WebUI。

## 使用
- 启动 WebUI 后，进入 `txt2img` 或 `img2img` 页面，工具栏会出现两个新图标：
  - 保存默认：图标为样式/保存符号，提示为“保存当前页面为默认”。
  - 卸载模型：图标为刷新符号，提示为“从缓存和内存中卸载所有模型”。
- 点击“保存默认”后，扩展会自动跳转设置页并完成保存、应用与重载。
- 点击“卸载模型”后，控制台会输出结果信息；首次再次生成图片时会重新加载模型。

## 兼容性
- 基于 A1111 reForge 的内部模块：`modules.script_callbacks`、`modules.ui_components.ToolButton`、`modules.ui.save_style_symbol`、`modules.ui.refresh_symbol`、`sd_models`、`shared` 等。
- GPU 环境下会尝试调用 `torch.cuda.empty_cache()`；CPU-only 环境自动跳过。

## 注意事项
- 卸载模型会清空当前模型与相关缓存；下一次生成将触发重新加载，可能产生短暂延时。
- 某些第三方 LoRA/额外网络扩展的内部状态若不兼容，可能无法被完全清理。
- 若看不到按钮，请尝试点击“重载 UI”或重启 WebUI。

## 常见问题
- 保存默认后未生效：请确认 Settings 页面存在 Defaults 分页，并且界面已成功重载。
- 卸载失败或报错：查看控制台输出，确认无第三方扩展冲突；必要时重启 WebUI。
- 显存未释放：确保当前无其它推理任务运行，必要时等待片刻或重启。

## 开发与贡献
- 主要脚本：`scripts/save_defaults_button.py`
- 通过 `script_callbacks.on_after_component` 在组件创建后注入按钮。
- 可按需调整按钮的 `elem_id`、`tooltip` 与前端自动化流程。

## 许可证
- 暂未声明。

---

## English Version

sd-webui-save-default-page is a lightweight extension for Stable Diffusion WebUI (reForge/A1111) that injects two convenient buttons into the `txt2img` and `img2img` toolbars:

- Save current page as defaults (automates navigating to Settings → Defaults → Save/Apply → Apply settings → Reload UI)
- Unload models from cache and memory (unload weights, clear LoRA/extra networks states, VAE, CUDA cache, etc.)

### Features
- Save Defaults: automatically performs Settings → Defaults save & apply, then reloads the UI.
- Unload Model Cache: safely unloads current model weights and related caches without breaking system modules as much as possible.

### Installation
- Place this extension folder under your Stable Diffusion WebUI `extensions` directory, for example:
  - `stable-diffusion-webui/extensions/sd-webui-save-default-page`
- Restart or reload the WebUI.

### Usage
- After WebUI starts, go to `txt2img` or `img2img`. Two new icons appear in the toolbar:
  - Save Defaults: a style/save icon, tooltip "Save current page as default".
  - Unload Models: a refresh icon, tooltip "Unload all models from cache and memory".
- Clicking "Save Defaults" triggers automatic navigation to Settings and completes save, apply, and UI reload.
- Clicking "Unload Models" prints status messages in the console; the next generation will reload models on demand.

### Compatibility
- Uses A1111 reForge internal modules: `modules.script_callbacks`, `modules.ui_components.ToolButton`, `modules.ui.save_style_symbol`, `modules.ui.refresh_symbol`, `sd_models`, `shared`.
- On GPU, tries `torch.cuda.empty_cache()`; skipped on CPU-only.

### Notes
- Unloading models clears current model and caches; next generation reloads them, which may add a short delay.
- Some third-party LoRA/extra network extensions may keep internal states that cannot be fully cleared.
- If the buttons do not appear, try "Reload UI" or restart the WebUI.

### FAQ
- Defaults not applied: ensure the Settings page has a Defaults tab and the UI was reloaded successfully.
- Unload failed or errors: check console output, verify no conflicts with third-party extensions; restart WebUI if needed.
- VRAM not freed: ensure no other inference tasks are running; wait a bit or restart.

### Development & Contribution
- Main script: `scripts/save_defaults_button.py`
- Buttons are injected after components via `script_callbacks.on_after_component`.
- You can adjust button `elem_id`, `tooltip`, and frontend automation as needed.

### License
- Not declared yet.

