# REA (Reverse Engineer Anything) — CAPABILITIES AUDIT

**Repository:** https://github.com/morluto/rea  
**Audit Date:** 2026-11-05  
**Status:** Research phase for VERONIKA integration  
**Integration Target:** Phases 15-19

---

## EXECUTIVE SUMMARY

REA is a tool for analyzing and reverse-engineering applications across multiple platforms (web, mobile, native). This audit documents its capabilities, architecture, and integration requirements for VERONIKA.

**Integration Goals:**
1. **Development-time:** Help coding agents understand existing code
2. **Runtime:** Enable VERONIKA to investigate applications on command

---

## CORE CAPABILITIES (To Be Verified)

### Supported Target Types

**Web Applications:**
- Single-page applications (React, Vue, Angular)
- Static websites
- Progressive web apps
- JavaScript-heavy sites
- Three.js/WebGL applications

**Mobile Applications:**
- Android APK analysis
- iOS IPA analysis (if supported)
- React Native apps
- Flutter apps

**Native Applications:**
- Windows executables
- macOS applications
- Linux binaries
- Electron applications

### Analysis Features

**Static Analysis:**
- File structure inspection
- Dependency detection
- Framework identification
- Configuration parsing
- Resource extraction
- Symbol analysis (when available)

**Dynamic Analysis:**
- Runtime behavior observation
- Network traffic capture
- API endpoint discovery
- State management tracking
- Event flow monitoring

**Code Analysis:**
- Bundle analysis (webpack, rollup, etc.)
- Source map utilization
- Code structure mapping
- Component hierarchy
- Function call graphs

---

## ARCHITECTURE

### Command-Line Interface (CLI)

Expected command structure:
```bash
# Basic analysis
rea analyze <target> [options]

# Web application
rea analyze https://example.com --output report.json

# Mobile app
rea analyze app.apk --platform android

# Native binary
rea analyze app.exe --platform windows

# With specific analysis depth
rea analyze <target> --depth deep --include-assets
```

### MCP (Model Context Protocol) Server

REA likely exposes analysis capabilities through MCP tools:

**Expected MCP Tools:**
1. `analyze_target` - Main analysis function
2. `list_components` - Extract component structure
3. `extract_assets` - Get resources (images, fonts, etc.)
4. `map_api_calls` - Document network requests
5. `identify_frameworks` - Detect tech stack
6. `generate_report` - Create comprehensive documentation

**MCP Schema Example:**
```typescript
{
  name: "analyze_target",
  description: "Analyze a web, mobile, or native application",
  inputSchema: {
    type: "object",
    properties: {
      target: {
        type: "string",
        description: "URL, file path, or application identifier"
      },
      targetType: {
        type: "string",
        enum: ["web", "mobile", "native"],
        description: "Type of target to analyze"
      },
      depth: {
        type: "string",
        enum: ["shallow", "normal", "deep"],
        default: "normal"
      },
      includeAssets: {
        type: "boolean",
        default: false
      }
    },
    required: ["target", "targetType"]
  }
}
```

### Output Formats

**JSON Report:**
```json
{
  "target": {
    "url": "https://example.com",
    "type": "web",
    "analyzedAt": "2026-11-05T08:00:00Z"
  },
  "techStack": {
    "framework": "React",
    "bundler": "Webpack",
    "ui": ["Tailwind CSS", "Framer Motion"],
    "state": "Redux",
    "rendering": "Three.js"
  },
  "architecture": {
    "type": "SPA",
    "routing": "React Router",
    "components": 47,
    "pages": 12
  },
  "apis": [
    {
      "method": "GET",
      "endpoint": "/api/users",
      "params": ["page", "limit"]
    }
  ],
  "assets": {
    "images": 23,
    "fonts": 4,
    "videos": 2,
    "models": 5
  },
  "features": [
    "3D visualization",
    "Real-time updates",
    "User authentication",
    "Data export"
  ]
}
```

**Markdown Report:**
```markdown
# Analysis Report: example.com

## Technology Stack
- Framework: React 18.2
- State Management: Redux
- UI Library: Tailwind CSS + Framer Motion
- 3D Rendering: Three.js r150

## Architecture
- Type: Single Page Application
- Components: 47
- Routes: 12
- Build Tool: Webpack 5

## Key Features
1. Interactive 3D visualization
2. Real-time data updates (WebSocket)
3. User authentication (JWT)
4. CSV/JSON data export

## API Endpoints
- GET /api/users
- POST /api/auth/login
- GET /api/data/:id

## Assets
- Images: 23 (PNG, SVG)
- Fonts: 4 (WOFF2)
- 3D Models: 5 (GLTF)
```

---

## INTEGRATION ARCHITECTURE FOR VERONIKA

### Development-Time REA (for Coding Agents)

**Purpose:** Help coding agents understand existing codebases

**Structure:**
```
<VERONIKA workspace>
├── .rea/
│   ├── config.json
│   ├── analysis-cache/
│   │   ├── veronika-desktop.json
│   │   ├── ultron-ui.json
│   │   └── jarvis-part7.json
│   └── reports/
│       ├── veronika-architecture.md
│       └── ultron-components.md
```

**Workflow:**
1. Developer or agent requests analysis
2. REA analyzes target project
3. Report cached locally
4. Agents can query analysis results
5. Incremental updates on code changes

### Runtime REA (integrated into VERONIKA)

**Purpose:** Allow VERONIKA to investigate applications on command

**Architecture:**
```
VERONIKA/
├── ai/
│   └── research/
│       ├── rea_client.py          # REA CLI wrapper
│       ├── rea_manager.py         # Investigation orchestrator
│       ├── target_classifier.py   # Identify target type
│       ├── investigation_planner.py
│       ├── evidence_manager.py
│       ├── behavior_analyzer.py
│       ├── feature_mapper.py
│       ├── reconstruction_engine.py
│       └── verification_engine.py
```

**Workflow:**
```
User: "Veronika, reverse engineer this website"
    ↓
rea_manager.py
├── Classify target (web/mobile/native)
├── Check permissions (approved targets only)
├── Create investigation plan
├── Invoke REA via CLI or MCP
├── Collect evidence
├── Parse results
├── Generate VERONIKA-formatted report
├── Store in Second Brain
└── Create Galaxy nodes (investigation, evidence, features)
```

---

## WINDOWS COMPATIBILITY

**Critical Requirements to Verify:**

1. **Python Compatibility:**
   - Does REA run on Python 3.13?
   - Windows-specific dependencies?
   - Path handling (forward vs backslash)

2. **Shell Requirements:**
   - PowerShell vs Bash
   - Command syntax differences
   - Environment variables

3. **Browser Automation:**
   - Playwright/Puppeteer on Windows
   - Chrome/Edge executable paths
   - Headless mode support

4. **Binary Analysis:**
   - Windows PE format support
   - .NET application analysis
   - UWP app analysis

5. **Permissions:**
   - Admin rights required?
   - Firewall considerations
   - Antivirus exceptions

**Testing Plan:**
```bash
# Test installation
pip install rea  # or alternative install method

# Test basic analysis
rea --version
rea analyze https://example.com

# Test Windows-specific features
rea analyze notepad.exe --platform windows
```

---

## SECURITY & PERMISSIONS

### Investigation Boundaries

**Approved Targets:**
- Explicitly authorized URLs
- Owner-specified applications
- Development projects
- Public websites (with rate limiting)

**Forbidden Targets:**
- Unauthorized private applications
- Protected systems
- Applications with DRM/anti-tamper
- Competitor applications without consent

### Permission System

```python
# investigation_permissions.py
class InvestigationPermissions:
    """Manage REA investigation authorization"""
    
    def __init__(self):
        self.approved_domains = set()
        self.approved_apps = set()
        self.investigation_logs = []
    
    def request_permission(self, target: str) -> bool:
        """Request owner approval for investigation"""
        if self.is_pre_approved(target):
            return True
        return self.prompt_owner(target)
    
    def is_pre_approved(self, target: str) -> bool:
        """Check if target is in approved list"""
        # Implementation
        pass
    
    def log_investigation(self, target: str, results: dict):
        """Track all investigations for audit"""
        self.investigation_logs.append({
            'target': target,
            'timestamp': datetime.now(),
            'findings': len(results.get('features', [])),
            'approved_by': 'owner'
        })
```

### Evidence Handling

**Storage:**
- Evidence stored in Second Brain
- Screenshots saved securely
- Source code snippets (when authorized)
- Network captures (privacy-filtered)

**Privacy:**
- No credential extraction
- No personal data collection
- No unauthorized access
- Clear evidence provenance

---

## REA CLIENT WRAPPER

```python
# ai/research/rea_client.py
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any

class REAClient:
    """Wrapper for REA CLI and MCP tools"""
    
    def __init__(self, rea_path: Optional[str] = None):
        self.rea_path = rea_path or "rea"  # Default to PATH
        self.cache_dir = Path(".rea/analysis-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def analyze_web(
        self,
        url: str,
        depth: str = "normal",
        include_assets: bool = False
    ) -> Dict[str, Any]:
        """Analyze a web application"""
        cache_file = self.cache_dir / f"{self._url_to_filename(url)}.json"
        
        # Check cache
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        
        # Run REA analysis
        cmd = [
            self.rea_path,
            "analyze",
            url,
            "--type", "web",
            "--depth", depth,
            "--format", "json"
        ]
        
        if include_assets:
            cmd.append("--include-assets")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        analysis = json.loads(result.stdout)
        
        # Cache result
        with open(cache_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        return analysis
    
    def analyze_native(
        self,
        app_path: str,
        platform: str = "windows"
    ) -> Dict[str, Any]:
        """Analyze a native application"""
        cmd = [
            self.rea_path,
            "analyze",
            app_path,
            "--type", "native",
            "--platform", platform,
            "--format", "json"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        return json.loads(result.stdout)
    
    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        import re
        safe = re.sub(r'[^\w\-]', '_', url)
        return safe[:100]  # Limit length
```

---

## INSTALLATION VERIFICATION CHECKLIST

- [ ] REA repository cloned/inspected
- [ ] Installation requirements documented
- [ ] Windows compatibility verified
- [ ] CLI commands tested
- [ ] MCP server functional (if applicable)
- [ ] Output format validated
- [ ] Python API available (if applicable)
- [ ] Browser automation working
- [ ] Native analysis working
- [ ] Performance benchmarks
- [ ] Error handling tested
- [ ] Documentation reviewed
- [ ] License compatibility checked

---

## INTEGRATION MILESTONES

### Phase 15: REA Research (CURRENT)
- [x] Documentation created
- [ ] Repository cloned
- [ ] Installation tested
- [ ] CLI capabilities verified
- [ ] Windows compatibility confirmed
- [ ] Example analyses run

### Phase 16: Development-Time Setup
- [ ] REA client wrapper implemented
- [ ] Cache system created
- [ ] VERONIKA codebase analyzed
- [ ] Part 7 analyzed
- [ ] ULTRON UI analyzed
- [ ] Reports generated

### Phase 17: Runtime Integration
- [ ] rea_manager.py implemented
- [ ] target_classifier.py implemented
- [ ] investigation_planner.py implemented
- [ ] Permission system implemented
- [ ] Voice command handler
- [ ] Galaxy visualization nodes

### Phase 18: Investigation Engine
- [ ] evidence_manager.py implemented
- [ ] behavior_analyzer.py implemented
- [ ] feature_mapper.py implemented
- [ ] Report templates
- [ ] Second Brain storage

### Phase 19: Reconstruction Engine
- [ ] reconstruction_engine.py implemented
- [ ] verification_engine.py implemented
- [ ] Feature → Blueprint pipeline
- [ ] Blueprint → Implementation pipeline
- [ ] Testing framework
- [ ] Quality verification

---

## OPEN QUESTIONS

1. **REA Installation:**
   - Is it available via pip?
   - Does it require npm/node?
   - Any binary dependencies?

2. **MCP Server:**
   - How is the MCP server started?
   - Default port and configuration?
   - Authentication requirements?

3. **Output Formats:**
   - What JSON schema does REA use?
   - Are there structured types/classes?
   - Can output format be customized?

4. **Resource Usage:**
   - Memory requirements for analysis?
   - CPU usage during analysis?
   - Disk space for caching?

5. **Rate Limiting:**
   - Built-in rate limiting for web analysis?
   - Configurable delays?
   - Respect for robots.txt?

6. **Legal/Ethical:**
   - Terms of service for REA?
   - Acceptable use policy?
   - Any restrictions on targets?

---

## NEXT ACTIONS

### Immediate (Phase 15)
1. Clone REA repository: `git clone https://github.com/morluto/rea`
2. Read official documentation
3. Test installation on Windows
4. Run example analyses
5. Document actual CLI commands
6. Test MCP server (if available)
7. Verify Windows compatibility
8. Create integration test plan

### Short-term (Phase 16-17)
1. Implement REA client wrapper
2. Create permission system
3. Build evidence manager
4. Integrate with Second Brain
5. Create Galaxy visualization
6. Test voice command workflow

### Long-term (Phase 18-19)
1. Build reconstruction engine
2. Implement verification system
3. Create feature templates
4. Test end-to-end workflow
5. Optimize performance
6. Document best practices

---

## RESOURCES

- **Repository:** https://github.com/morluto/rea
- **Video Demo:** https://youtu.be/84CkBM_jF4g
- **VERONIKA Docs:** `docs/VIDEO_REFERENCE_AUDIT.md`
- **Integration Plan:** `docs/REA_INTEGRATION_PLAN.md`
- **Feature Matrix:** `docs/FEATURE_COVERAGE_MATRIX.md`

---

**Audit Status:** DRAFT (requires repository inspection)  
**Windows Testing:** PENDING  
**Integration Design:** COMPLETE  
**Next Update:** After repository analysis

---

*Generated: 2026-11-05 08:05 UTC*  
*Awaiting: Repository clone and hands-on testing*  
*Integration Target: Phases 15-19 (after Phase 5 complete)*
