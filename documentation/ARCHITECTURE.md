# CITADEL Modular Architecture Guide

CITADEL separates core platform services from independent tool modules so new utilities can be added without modifying the main application shell or Tool Library layout.

## Directory Layout

```
CITADEL/
├── main.py                              # Unified FastAPI entry point
├── backend/
│   ├── core/
│   │   ├── config.py                    # Platform settings & upload limits
│   │   └── security.py                  # Security headers & sanitized errors
│   └── module_manager/
│       ├── registry.py                  # ModuleDefinition & ModuleRegistry
│       └── modules_config.py            # Declarative module registration
├── modules/
│   └── steganography_system/            # Module 01 (preserved existing project + router.py adapter)
├── frontend/
│   ├── index.html                       # SPA shell (enables continuous background audio)
│   ├── js/router.js                     # Client-side router
│   ├── components/                      # navbar, footer, theme-toggle, music-player, tool-card
│   ├── pages/                           # home, tools, steganography, about, credits, contact, policy
│   └── styles/                          # dark-theme.css, light-theme.css, base.css
├── assets/
│   ├── logos/                           # Original Citadel logos & favicon
│   └── music/                           # Citadel background theme audio
├── tests/                               # End-to-end CITADEL platform tests
└── documentation/
```

## How to Add a New Module (e.g., Module 02)

1. **Create the module folder**: Place the new tool's backend code inside `modules/<module_name>/` and expose a `create_router() -> APIRouter` function in `modules/<module_name>/router.py`.
2. **Register it in `backend/module_manager/modules_config.py`**:
   ```python
   registry.register(
       ModuleDefinition(
           module_id="my-new-tool",
           code="MODULE 02",
           name="My New Tool",
           description="Short description of what the tool does.",
           category="Security / Utility",
           icon="default",
           entry_route="/tools/my-new-tool",
           status="Available",
           version="1.0.0",
           backend=ModuleBackendConfig(
               api_prefix="/api/modules/my-new-tool",
               router_factory=my_router_mod.create_router,
               health_endpoint="/api/modules/my-new-tool/health",
           ),
           capabilities=["Capability A", "Capability B"],
       )
   )
   ```
3. **Add the frontend view**: Create `frontend/pages/my-new-tool.js` and register its route in `frontend/js/router.js`.
4. **Automatic discovery**: The Tools Library (`/tools`) fetches `/api/modules` dynamically, so the new tool card renders automatically with zero changes to `tools.js` or `main.py`.
