# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for excellon-rpa.exe (main pipeline)."""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden_imports = [
    # langgraph / langchain internals
    *collect_submodules("langgraph"),
    *collect_submodules("langchain_core"),
    # pywinauto backends
    *collect_submodules("pywinauto"),
    # pydantic
    *collect_submodules("pydantic"),
    *collect_submodules("pydantic_settings"),
    # anthropic SDK (Claude Haiku 4.5 vision fallback)
    *collect_submodules("anthropic"),
    # OCR fallback for module clicking (RapidOCR + ONNX runtime)
    *collect_submodules("rapidocr_onnxruntime"),
    *collect_submodules("onnxruntime"),
    # agent modules (dynamically imported in main.py and routes.py)
    "agents.agent1_login.graph",
    "agents.agent1_login.nodes.launch_app",
    "agents.agent1_login.nodes.wait_for_login_screen",
    "agents.agent1_login.nodes.type_credentials",
    "agents.agent1_login.nodes.press_connect",
    "agents.agent1_login.nodes.handle_popups_pre",
    "agents.agent1_login.nodes.wait_for_fullscreen",
    "agents.agent1_login.nodes.handle_popup_post",
    "agents.agent1_login.nodes.verify_home_screen",
    "agents.agent2_navigation.graph",
    "agents.agent2_navigation.nodes.read_config",
    "agents.agent2_navigation.nodes.focus_window",
    "agents.agent2_navigation.nodes.click_module",
    "agents.agent2_navigation.nodes.type_search",
    "agents.agent2_navigation.nodes.collect_results",
    "agents.agent2_navigation.nodes.exact_match",
    "agents.agent2_navigation.nodes.visual_confirm",
    "agents.agent2_navigation.nodes.click_item",
    "agents.agent2_navigation.nodes.verify_opened",
    "agents.agent3_filter.graph",
    "agents.agent3_filter.nodes.click_arrow_button",
    "agents.agent3_filter.nodes.select_dealer",
    "agents.agent3_filter.nodes.handle_tax_checkboxes",
    "agents.agent3_filter.nodes.select_date_range_custom",
    "agents.agent3_filter.nodes.enter_from_date",
    "agents.agent3_filter.nodes.enter_to_date",
    "agents.agent3_filter.nodes.enter_as_on_date",
    "agents.agent3_filter.nodes.press_generate_report",
    "agents.agent4_download.graph",
    "agents.agent4_download.nodes.click_export_button",
    "agents.agent4_download.nodes.dismiss_export_popup",
    "agents.agent4_download.nodes.handle_save_as",
    "agents.agent4_download.nodes.decline_open_file",
    "agents.agent4_download.nodes.close_application",
    # automation & vision
    "automation.window_manager",
    "automation.screenshot",
    "automation.keyboard_mouse",
    "automation.search_handler",
    "automation.ui_tree_reader",
    "automation.uia_retry",
    "automation.ocv_text_finder",
    "automation.popup_handler",
    "automation.file_explorer_handler",
    "vision.highlight_detector",
    "vision.gemini_verifier",
    "vision.anthropic_verifier",
    "vision.local_disambiguator",
    "vision.ocr_module_finder",
    # config
    "config.settings",
    "config.report_loader",
    # api
    "api.main",
    "api.routes",
    "api.schemas",
    # other
    "uvicorn",
    "fastapi",
    "google.generativeai",
    "anthropic",
    "rapidocr_onnxruntime",
    "onnxruntime",
    *collect_submodules("cv2"),
    *collect_submodules("PIL"),
    *collect_submodules("numpy"),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("assets", "assets"),
        (".secrets", "."),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="excellon-rpa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="excellon-rpa",
)
