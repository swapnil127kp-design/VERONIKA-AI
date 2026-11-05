# REA Capabilities Audit

**Repository:** https://github.com/morluto/rea  
**Package:** rea-agents  
**Version:** 6.8.0  
**License:** MIT  
**Audit Date:** 2026-11-05

## Executive Summary

REA (Reverse Engineer Anything) is a comprehensive reverse-engineering toolkit that connects AI agents to analysis tools for inspecting software artifacts without source code. It provides both a CLI interface and an MCP (Model Context Protocol) server for analyzing native binaries, JavaScript/Electron applications, .NET assemblies, Android APKs, firmware, websites, and 40+ other target types. All analysis runs locally, returning pseudocode, assembly, module relationships, and evidence-based findings.

**Key Strengths:**
- Extensive format support (40+ target types)
- Local-only analysis (privacy-focused)
- Evidence-based results with provenance tracking
- Dual interface (CLI + MCP server)
- Windows compatibility with native tooling
- Integration with multiple decompilers (Hopper, Ghidra, IDA, Kuna)

---

## 1. Installation Requirements

### 1.1 Platform Support

**Primary Platforms:**
- Linux (with procps-compatible `ps`)
- macOS
- **Windows** (Windows 11 Pro tested, native Windows support via `rea-windows-x64.node`)

### 1.2 Runtime Requirements

**Node.js Versions (strict requirements):**
```
Node.js: ^22.23.4 || ^24.22.1 || >=26.12.1
npm: 11.16.0 (packageManager)
```

**Package Type:** ES Module (`"type": "module"`)

### 1.3 Installation Methods

**Quick Setup (recommended):**
```bash
npx rea-agents setup
```
This command:
- Registers REA with your agent
- Installs workflow instructions
- Backs up existing configuration
- Requires approval before making changes
- Supports automatic Hopper installation (with approval)

**Global Installation:**
```bash
npm install --global rea-agents
rea --help
```

**One-off Analysis (no installation):**
```bash
npx -y rea-agents@latest analyze-javascript-application /path/to/app --json
```

### 1.4 Windows-Specific Considerations

- Native Windows addon: `rea-windows-x64.node` (included in package)
- Verification script: `scripts/verify-windows-native-artifact.mjs`
- Windows Ghidra support with dedicated fixtures
- PowerShell-compatible commands for profile management

### 1.5 Update Process

```bash
# Update globally installed version
rea update

# Update via npx
npx rea-agents@latest setup
```

---

## 2. CLI Commands and Capabilities

### 2.1 Core Commands

**Setup and Configuration:**
```bash
rea setup [options]              # Configure agent connections
rea setup --client <name>        # Configure specific client
rea setup --all-detected         # Configure all detected agents
rea setup --dry-run              # Preview changes without applying
rea setup --json                 # Output plan as JSON
rea setup --yes                  # Auto-approve (requires explicit scope)
rea setup --install-hopper       # Non-interactive Hopper installation
```

**Analysis Commands:**
```bash
rea analyze <path>                                    # Auto-detect format and analyze
rea analyze-javascript-application <path> [--json]    # JavaScript/Electron apps
rea analyze-function <binary> <function>              # Analyze specific function
rea list-procedures <binary>                          # List all functions
rea inspect-artifact <path>                           # Artifact inspection
rea inspect-analysis-view <view-json>                 # Project analysis views
```

**Comparison Commands:**
```bash
rea compare-artifacts <path1> <path2>    # Compare two artifacts
rea compare-functions <func1> <func2>    # Compare functions
rea match-native-functions <opts>        # Match functions across binaries
```

**Evidence Management:**
```bash
rea get-evidence-bundle [options]        # Export session evidence
rea get-call-graph <binary> <function>   # Extract call graph
rea trace-call-path <opts>               # Trace execution paths
rea trace-feature <opts>                 # Feature tracing
```

**Diagnostic Commands:**
```bash
rea doctor [--json]                      # Health diagnostics
rea doctor --client <name> --skill       # Verify client + skill
rea config:print                         # Show MCP configuration
```

**Process and Runtime:**
```bash
rea mcp                                  # Start MCP server
rea --help                               # Show all commands
rea --version                            # Show version
```

### 2.2 Command Options

**Common Flags:**
- `--json` - Output structured JSON results
- `--provider <name>` - Select analysis provider (hopper, ghidra, ida, kuna)
- `--detail <level>` - Control output detail (summary, complete)
- `--dry-run` - Preview without executing
- `--accessible` - Sequential, vertical prompts for accessibility
- `NO_COLOR=1` - Disable colored output

**Client Selection:**
- `--client claude_code` - Claude Code
- `--client codex` - Codex
- `--client cursor` - Cursor
- `--client gemini_cli` - Gemini CLI
- `--client grok_build` - Grok Build

### 2.3 Output Formats

**Evidence Records:**
- Complete canonical Evidence records in JSON
- `structuredContent.normalized_result` - Parsed results
- `structuredContent.evidence_id` - Unique identifier
- `raw_result` - Provider-specific original output (or null)
- `analysis_profile` - Analysis configuration

**Result Streaming:**
- Text output to stderr (progress, prompts)
- Structured JSON to stdout (parseable)
- Supports piping: `rea analyze app --json > evidence.json`

---

## 3. MCP Server Tools and Schemas

### 3.1 MCP Server Identity

**Package Name:** `io.github.morluto/rea`  
**Server Command:** `node scripts/plugin-mcp-launcher.mjs <version>`

### 3.2 Tool Categories

**Evidence-Producing Tools** (return complete Evidence records):
- Analysis operations
- Inspection operations
- Comparison operations
- All return `structuredContent` with validated schemas

**Result Format:**
```json
{
  "structuredContent": {
    "normalized_result": { /* operation-specific result */ },
    "evidence_id": "unique-identifier",
    "analysis_profile": { /* profile or null */ }
  },
  "raw_result": null  // or provider-specific data
}
```

### 3.3 Core MCP Tools

**Binary Analysis:**
```
analyze_function(binary, function, options)
  - Returns: Function dossier with pseudocode, assembly, calls
  - Facets: pseudocode, assembly, comments, callers, callees, 
            references, strings_names, cfg
  - Supports: detail levels, provider selection

list_procedures(binary, options)
  - Returns: Complete function inventory
  - Includes: addresses, names, types, metadata

get_call_graph(binary, function, depth)
  - Returns: Call graph keyed by depth
  - Includes: relationship coverage, limitations
```

**Artifact Operations:**
```
inspect_artifact(path, options)
  - Returns: Artifact inventory and metadata
  - Coverage: root scope or container-entries
  - Status: complete or unknown

compare_artifacts(source1, source2, options)
  - Source types: retained-evidence, evidence-file, inline
  - Returns: Delta analysis with coverage
  - Validates: matching scopes, complete graphs

inspect_analysis_view(view_spec)
  - Projects: summary, module page, single module
  - Sources: inline evidence or evidence-file path
```

**Function Comparison:**
```
compare_functions(func1, func2, options)
  - Compares: pseudocode, assembly, calls, strings
  - Returns: Dimension-wise comparison (changed/unchanged/unknown)
  - Supports: retained evidence references

match_native_functions(left_obs, right_obs, options)
  - Pairs functions across binaries
  - Preserves: aliases, unknowns, fact pages
```

**Path and Feature Tracing:**
```
trace_call_path(binary, start, goal, options)
  - Returns: Paths between functions
  - Status: reached, not_reached, unknown, truncated
  - Includes: residual_unknowns

trace_feature(binary, references, options)
  - Traces feature implementation
  - Validates: containing-procedure resolution
```

**Session Management:**
```
get_evidence_bundle(options)
  - Exports: retained session evidence
  - Format: authenticated bundle
  - Use: transfer, comparison, archival

close_binary(binary)
  - Cleanup: provider resources
  - Retry: on cleanup_incomplete error
```

### 3.4 Input Schema Patterns

**Evidence Sources:**
```json
{
  "kind": "retained-evidence",
  "evidence_id": "id-from-session"
}
// or
{
  "kind": "evidence-file", 
  "path": "/absolute/path/evidence.json",
  "evidence_id": "optional-selector"  // for bundles with multiple records
}
// or inline complete Evidence object
```

**Analysis Profiles:**
```json
{
  "provider": "ghidra",  // or hopper, ida, kuna
  "options": {
    // provider-specific configuration
  }
}
```

### 3.5 Output Schema Characteristics

**Facet Availability:**
```json
{
  "facet_availability": {
    "pseudocode": { "available": true },
    "assembly": { "available": true },
    "callers": { "available": false, "reason": "decompiler failure" }
  }
}
```

**Coverage Declaration:**
```json
{
  "coverage": {
    "scope": "root",  // or "container-entries"
    "status": "complete"  // or "unknown"
  }
}
```

**Error Handling:**
```json
{
  "isError": true,
  "content": "{\"error\": {...}}"  // canonical diagnostic
  // No structuredContent on errors
}
```

**Recovery Hints:**
- `recovery.kind = "inspect_input_contract"` - Re-read tool schema
- `recovery.kind = "inspect_timeout_state"` - Check timeouts
- `recovery.kind = "retry_cleanup"` - Cleanup will retry

### 3.6 Environment Variables

**MCP Server Configuration:**
```bash
REA_MCP_INPUT_SCHEMA_PROFILE      # Input schema validation level
REA_MCP_OUTPUT_SCHEMA_PROFILE     # Output schema validation level
REA_MCP_MAX_RESPONSE_BYTES        # Response size limit
REA_MCP_TOOL_FAMILIES             # Enabled tool groups
```

**Profile Management (Claude Code):**
```bash
CLAUDE_CONFIG_DIR=~/.claude-rea   # Isolate REA to specific profile
```

---

## 4. Supported Target Types

### 4.1 Native Binaries

**Executable Formats:**
- ELF (Linux, embedded systems)
- PE/PE+ (Windows executables, DLLs)
- Mach-O (macOS, iOS)
- Mach-O Fat/Universal binaries
- DOS executables
- GameCube DOL
- PSP executables
- Nintendo Switch (NSO/NRO)
- Raw binary blobs

**Architectures:**
- x86/x86-64 (Intel/AMD)
- ARM/ARM64/AArch64
- MIPS (including soft-float)
- PowerPC
- RISC-V
- 6502
- M68000
- WebAssembly

**Binary Metadata:**
- PE certificates and signatures
- PE imports and load configuration
- ELF notes and section metadata
- Linux kernel modules
- Go binary metadata
- Rust dependency information
- NativeAOT compilation artifacts

### 4.2 JavaScript and Web

**JavaScript Applications:**
- Standalone JavaScript apps
- Electron applications (ASAR archives)
- Node.js SEA (Single Executable Applications)
- Bun standalone executables
- Extracted application directories

**JavaScript Analysis Features:**
- Application dependency graph
- Module references and relationships
- Route inventory
- Native API handoffs
- Source recovery and reconstruction
- Runtime observation and reconciliation

**Web Analysis:**
- Websites (via browser observation)
- Chrome DevTools Protocol (CDP) captures
- HTTP/1.1, HTTP/2, HTTP/3 network captures
- HAR (HTTP Archive) files
- PCAP packet captures
- QLOG captures
- Source maps and location tracing
- Module traces
- Script exports

**Browser Features:**
- Runtime observation via Playwright
- DOM analysis
- Network traffic capture
- Request/response analysis
- WebSocket inspection
- Source map resolution

### 4.3 Managed Code and Packages

**.NET:**
- .NET assemblies (DLL, EXE)
- .NET bundles
- IL2CPP metadata
- NativeAOT binaries

**Python:**
- PyC bytecode files
- PyInstaller packages
- Python packaged applications

**Other:**
- Erlang BEAM bytecode
- EVM (Ethereum) bytecode
- Solidity metadata
- Java (via JADX - Android context)

### 4.4 Mobile Platforms

**Android:**
- APK files
- Android App Bundles
- DEX bytecode
- Native libraries (.so)
- Android manifests
- APK signatures (v1-v4)
- Apktool resource analysis
- JNI library inventory
- ProGuard/R8 mapping files

**Android Tooling:**
- ADB device analysis
- On-device file acquisition
- Runtime instrumentation via Frida

**Apple:**
- IPA files
- macOS applications (.app bundles)
- iOS applications
- Asset catalogs
- Interface Builder files (XIB/NIB)
- Keyed archives
- IPS crash reports
- Dispatch queues analysis

**Other Mobile:**
- HarmonyOS HAP files
- Flutter applications
- Unity mobile builds

### 4.5 Firmware and Embedded

**Firmware Formats:**
- U-Boot uImage
- UF2 (USB Flashing Format)
- DfuSe firmware
- ESP32/ESP8266 images
- ESP flash images
- Device Tree binaries (DTB)
- FIT images
- Intel HEX records
- iNES ROM containers

**Embedded Platforms:**
- ESP32/ESP8266 (Espressif)
- Microcontroller firmware
- RISC-V embedded systems
- ARM Cortex-M
- GPU code objects (AMDGPU)

### 4.6 Game Engines and Containers

**Game Assets:**
- Godot PCK archives
- Unity UnityFS archives
- WeChat Mini Program packages (wxapkg)

**Archive Formats:**
- ASAR (Electron)
- SQLite databases
- ZIP archives
- Generic container analysis

### 4.7 Development Artifacts

**Process and Runtime:**
- Process captures (command execution)
- Desktop application captures (Linux)
- Recorded crashes and core dumps
- Signal recordings
- Application state snapshots

**Network Captures:**
- PCAP/PCAPNG files
- HTTP/3 and QUIC
- TLS-encrypted traffic (with keys)
- WebSocket streams
- QLOG protocol traces

---

## 5. Analysis Workflow

### 5.1 Development-Time Integration (Recommended)

**Architecture Pattern:**
```
Agent → REA MCP Server → Analysis Providers → Target Artifact
                       ↓
                   Evidence Database
```

**Workflow:**
1. Agent invokes MCP tool (e.g., `analyze_function`)
2. REA selects appropriate provider (Hopper, Ghidra, IDA)
3. Provider analyzes target locally
4. REA wraps result in Evidence record
5. Evidence retained in session
6. Agent receives structured result

**Key Characteristics:**
- Synchronous tool calls
- Evidence retention in session
- Provider abstraction
- Local-only execution
- No network transmission of code/data

### 5.2 Typical Analysis Flow

**Step 1: Target Identification**
```bash
# Desktop applications
rea analyze /path/to/app

# Specific binary analysis
rea list-procedures /path/to/binary
```

**Step 2: Deep Investigation**
```bash
# Analyze specific function
rea analyze-function /path/to/binary function_name --json

# Get call relationships
rea get-call-graph /path/to/binary entry_point --depth 3
```

**Step 3: Comparison**
```bash
# Compare two implementations
rea compare-functions evidence1.json evidence2.json

# Compare entire artifacts
rea compare-artifacts app_v1/ app_v2/
```

**Step 4: Evidence Management**
```bash
# Export findings
rea get-evidence-bundle --output bundle.json

# Project specific views
rea inspect-analysis-view summary.json
```

### 5.3 Agent-Driven Workflow

**Typical Agent Prompt:**
```
"Understand how [feature] works in [app], show evidence, 
and build a similar feature for my project."
```

**Agent Execution Path:**
1. Locate target application/binary
2. Call `inspect_artifact` for overview
3. Call `list_procedures` to find relevant functions
4. Call `analyze_function` for deep analysis
5. Call `trace_feature` to understand implementation
6. Synthesize findings into implementation plan
7. Reference Evidence IDs for verification

### 5.4 Provider Selection Strategy

**Automatic Selection:**
- JavaScript/Electron → Built-in static analysis
- Native binary → First available: Hopper > Ghidra > IDA > Kuna

**Manual Selection:**
```bash
rea analyze binary --provider ghidra
rea analyze binary --provider hopper
```

**Provider Characteristics:**

**Hopper** (macOS-focused):
- Fast analysis startup
- Excellent ARM/AArch64 support
- Commercial license
- Can be auto-installed by setup

**Ghidra** (open-source):
- Broad architecture support
- Extensible via Java plugins
- Ephemeral databases (no modification)
- Free, NSA-developed

**IDA** (industry standard):
- Read-only mode in REA
- Advanced analysis capabilities
- Commercial license required
- Bring-your-own installation

**Kuna** (specialized):
- Specific target support
- Documented in kuna-provider.md

### 5.5 Evidence Lifecycle

**Creation:**
- Every analysis produces Evidence record
- Includes: result, identity, profile, provenance

**Retention:**
- Session retains Evidence automatically
- Referenced by `evidence_id`
- Survives across tool calls

**Projection:**
- Large results can be summarized
- Use `inspect_analysis_view` for views
- Paging for large datasets

**Export:**
- `get_evidence_bundle` exports session
- Authenticated bundles preserve integrity
- Can be imported in future sessions

**Reuse:**
- Validated cache for identical inputs
- Snapshot reuse based on cache keys
- Invalidation on profile changes

---

## 6. Output Formats

### 6.1 Evidence Record Structure

**Complete Evidence Record:**
```json
{
  "structuredContent": {
    "normalized_result": {
      // Operation-specific parsed results
      "functions": [...],
      "modules": [...],
      "metadata": {...}
    },
    "evidence_id": "sha256-based-identifier",
    "analysis_profile": {
      "provider": "ghidra",
      "version": "10.3",
      "options": {...}
    },
    "facet_availability": {
      "pseudocode": { "available": true },
      "assembly": { "available": true },
      "callers": { "available": true }
    },
    "coverage": {
      "scope": "root",
      "status": "complete"
    },
    "limitations": [
      "Limited to static analysis",
      "Unknown runtime behavior"
    ]
  },
  "raw_result": null  // or provider-specific output
}
```

### 6.2 Function Dossier Format

**Complete Function Analysis:**
```json
{
  "function": {
    "name": "calculateHash",
    "address": "0x401000",
    "signature": "uint64_t calculateHash(const char* input)"
  },
  "pseudocode": {
    "language": "c",
    "source": "uint64_t calculateHash(const char* input) { ... }"
  },
  "assembly": {
    "instructions": [
      {
        "address": "0x401000",
        "mnemonic": "push",
        "operands": ["rbp"],
        "bytes": "55"
      }
    ]
  },
  "calls": {
    "outgoing": [
      { "target": "strlen", "address": "0x401050" }
    ],
    "incoming": [
      { "source": "main", "address": "0x400800" }
    ]
  },
  "references": [
    { "type": "data", "address": "0x404000", "name": "hash_table" }
  ],
  "strings": [
    { "value": "Invalid input", "address": "0x402000" }
  ],
  "control_flow": {
    "blocks": [...],
    "edges": [...]
  }
}
```

### 6.3 Artifact Inventory Format

**JavaScript Application:**
```json
{
  "format": "javascript_application",
  "entry_points": ["main.js", "renderer.js"],
  "modules": [
    {
      "path": "src/core/engine.js",
      "dependencies": ["crypto", "./utils"],
      "exports": ["Engine", "initialize"]
    }
  ],
  "native_modules": [
    {
      "name": "native_addon",
      "platform": "win32",
      "arch": "x64"
    }
  ],
  "graph": {
    "nodes": [...],
    "edges": [...]
  },
  "coverage": {
    "scope": "root",
    "status": "complete"
  }
}
```

**Native Binary:**
```json
{
  "format": "elf",
  "architecture": "x86_64",
  "sections": [
    { "name": ".text", "address": "0x400000", "size": 8192 }
  ],
  "symbols": [
    { "name": "main", "address": "0x401000", "type": "function" }
  ],
  "imports": ["libc.so.6"],
  "exports": ["public_api"],
  "metadata": {
    "compiler": "gcc 11.2.0",
    "stripped": false
  }
}
```

### 6.4 Comparison Output Format

**Function Comparison:**
```json
{
  "comparison": {
    "pseudocode": {
      "status": "changed",
      "changes": 12,
      "details": [...]
    },
    "assembly": {
      "status": "changed",
      "instruction_diff": {...}
    },
    "calls": {
      "status": "unchanged",
      "outgoing_count": 5,
      "incoming_count": 3
    },
    "strings": {
      "status": "unknown",
      "reason": "Decoding unavailable on one side"
    }
  },
  "overall": "changed"
}
```

**Artifact Comparison:**
```json
{
  "left": { "evidence_id": "..." },
  "right": { "evidence_id": "..." },
  "delta": {
    "modules_added": ["new_feature.js"],
    "modules_removed": ["deprecated.js"],
    "modules_changed": [
      {
        "path": "core.js",
        "content_changed": true,
        "exports_changed": false
      }
    ]
  },
  "coverage_match": true,
  "scope": "root"
}
```

### 6.5 Error and Diagnostic Format

**Error Response:**
```json
{
  "isError": true,
  "content": "{
    \"error\": {
      \"code\": \"target_not_found\",
      \"message\": \"Binary not found at specified path\",
      \"details\": {
        \"path\": \"/path/to/binary\",
        \"checked_locations\": [...]
      },
      \"remediation\": {
        \"action\": \"Verify path and file permissions\"
      },
      \"recovery\": {
        \"kind\": \"inspect_input_contract\",
        \"operation\": \"analyze_function\"
      }
    }
  }"
}
```

**Partial Results with Limitations:**
```json
{
  "normalized_result": { /* partial data */ },
  "limitations": [
    "Decompiler failed for 3 functions",
    "Call graph may be incomplete",
    "Static analysis only - runtime behavior unknown"
  ],
  "facet_availability": {
    "pseudocode": { 
      "available": false, 
      "reason": "Decompiler timeout after 30s"
    }
  }
}
```

---

## 7. Integration Architecture Options

### 7.1 Development-Time Integration (Primary)

**Architecture:**
```
┌─────────┐     MCP      ┌──────────┐     Provider API    ┌──────────┐
│  Agent  │ ◄─────────► │   REA    │ ◄────────────────► │  Hopper  │
│ (Claude)│              │  Server  │                     │  Ghidra  │
└─────────┘              └──────────┘                     │   IDA    │
                               │                          └──────────┘
                               │
                         ┌─────▼──────┐
                         │  Evidence  │
                         │  Session   │
                         └────────────┘
```

**Use Cases:**
- Agent-assisted reverse engineering
- Feature understanding and replication
- Security analysis
- Code archaeology
- Competitive analysis

**Configuration:**
```bash
# Setup for Claude Code
rea setup --client claude_code

# Setup for multiple agents
rea setup --client codex --client cursor
```

**Agent Integration Files:**
```
.claude-plugin/
  ├── plugin.json          # Plugin metadata
  └── marketplace.json     # Marketplace listing

.codex-plugin/
  ├── plugin.json          # Codex configuration
  └── mcp.json             # MCP server config

skills/
  └── reverse-engineer-anything/
      ├── skill.md         # Workflow instructions
      └── references/      # Reference documentation
```

### 7.2 CLI Integration

**Architecture:**
```
┌──────────┐     CLI     ┌──────────┐
│  Script  │ ──────────► │   REA    │
│  Human   │             │   CLI    │
└──────────┘             └──────────┘
```

**Use Cases:**
- Scripted analysis pipelines
- CI/CD integration
- Batch processing
- Human-driven investigation

**Example Pipeline:**
```bash
#!/bin/bash
# Analysis pipeline

# 1. Analyze application
rea analyze-javascript-application ./app --json > app-evidence.json

# 2. Extract summary
jq -c '{
  source: {kind: "inline", evidence: .},
  view: {kind: "summary"}
}' app-evidence.json > view.json

# 3. Get readable summary
rea inspect-analysis-view view.json

# 4. Deep dive on specific modules
rea inspect-analysis-view module-view.json
```

### 7.3 CI/CD Integration

**GitHub Actions Example:**
```yaml
name: Security Analysis

on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '22.23.4'
      
      - name: Analyze with REA
        run: |
          npx -y rea-agents@latest analyze \
            ./dist/app --json > analysis.json
      
      - name: Check for changes
        run: |
          npx -y rea-agents@latest compare-artifacts \
            ./baseline.json ./analysis.json
      
      - name: Upload evidence
        uses: actions/upload-artifact@v3
        with:
          name: analysis-evidence
          path: analysis.json
```

### 7.4 Runtime vs Dev-Time Considerations

**Development-Time (Recommended):**
- ✅ MCP server integration
- ✅ Interactive agent workflows
- ✅ Evidence retention across sessions
- ✅ Progressive analysis refinement
- ✅ Local-only, privacy-preserving

**Runtime (Not Supported):**
- ❌ REA is not a runtime monitoring tool
- ❌ No live process attachment (except Frida)
- ❌ No continuous behavioral analysis
- ❌ Analysis is snapshot-based

**Hybrid Approach (Runtime Capture + Dev Analysis):**
```bash
# 1. Capture runtime behavior
rea capture-process command args

# 2. Analyze captured data
rea analyze-capture capture.json

# 3. Compare with expectations
rea compare-artifacts expected.json capture.json
```

### 7.5 Profile Isolation (Claude Code)

**Dedicated Profile for REA:**
```bash
# Create isolated profile
CLAUDE_CONFIG_DIR=~/.claude-rea npx rea-agents setup --client claude_code

# Use REA profile
CLAUDE_CONFIG_DIR=~/.claude-rea claude
```

**Benefits:**
- Separate configuration
- Isolated skill installation
- Independent session history
- Project-specific setup

**PowerShell Equivalent:**
```powershell
$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-rea"
npx rea-agents setup --client claude_code
claude
```

### 7.6 Supported Agent Clients

**Fully Supported:**
- Claude Code (`claude_code`)
- Codex (`codex`)
- Cursor (`cursor`)
- Gemini CLI (`gemini_cli`)
- Grok Build (`grok_build`)
- DeepSeek Harness
- OpenCode
- Commandcode
- OMP Client
- GitHub Copilot
- Pi, Hermes (native agents)

**Configuration Preservation:**
- Setup preserves caller-owned settings
- Approval policies retained (Codex)
- Tool selections preserved
- Environment overrides maintained
- Comments in config files preserved

---

## 8. Code Examples and API Patterns

### 8.1 JavaScript Application Analysis

**Basic Analysis:**
```javascript
// Via CLI
const { execSync } = require('child_process');

const result = execSync(
  'rea analyze-javascript-application ./app --json',
  { encoding: 'utf8' }
);

const evidence = JSON.parse(result);
console.log('Modules:', evidence.normalized_result.modules.length);
console.log('Entry points:', evidence.normalized_result.entry_points);
```

**MCP Tool Call (from agent):**
```json
{
  "method": "tools/call",
  "params": {
    "name": "analyze_javascript_application",
    "arguments": {
      "target": "/absolute/path/to/app",
      "options": {
        "detail": "summary"
      }
    }
  }
}
```

### 8.2 Native Function Analysis

**CLI Workflow:**
```bash
# 1. List all functions
rea list-procedures ./binary --json > procedures.json

# 2. Find function of interest
jq '.normalized_result.procedures[] | 
    select(.name | contains("crypto"))' procedures.json

# 3. Analyze specific function
rea analyze-function ./binary "crypto_hash_sha256" \
    --provider ghidra --json > function-evidence.json

# 4. Extract pseudocode
jq '.normalized_result.pseudocode.source' function-evidence.json
```

**MCP Pattern with Retained Evidence:**
```json
// First call - analyze function
{
  "name": "analyze_function",
  "arguments": {
    "binary": "/path/to/binary",
    "function": "crypto_hash_sha256",
    "provider": "ghidra"
  }
}

// Response includes evidence_id
{
  "normalized_result": { ... },
  "evidence_id": "sha256:abc123..."
}

// Second call - compare with different implementation
{
  "name": "compare_functions",
  "arguments": {
    "left": {
      "kind": "retained-evidence",
      "evidence_id": "sha256:abc123..."
    },
    "right": {
      "kind": "retained-evidence", 
      "evidence_id": "sha256:def456..."
    }
  }
}
```

### 8.3 Call Graph Extraction

**Node.js Script:**
```javascript
import { spawn } from 'child_process';

async function getCallGraph(binary, entryPoint, depth = 5) {
  return new Promise((resolve, reject) => {
    const proc = spawn('rea', [
      'get-call-graph',
      binary,
      entryPoint,
      '--depth', depth.toString(),
      '--json'
    ]);
    
    let output = '';
    proc.stdout.on('data', data => output += data);
    proc.on('close', code => {
      if (code === 0) {
        resolve(JSON.parse(output));
      } else {
        reject(new Error(`Exit code ${code}`));
      }
    });
  });
}

// Usage
const graph = await getCallGraph('./app', 'main', 3);

// Traverse graph by depth
for (const [depth, nodes] of Object.entries(graph.graph)) {
  console.log(`Depth ${depth}:`);
  for (const node of nodes) {
    console.log(`  ${node.function.name}`);
    console.log(`    Calls: ${node.calls.length}`);
    console.log(`    Coverage: ${node.relationship_coverage}`);
  }
}
```

### 8.4 Evidence Bundle Management

**Export and Import:**
```bash
# Export session evidence
rea get-evidence-bundle --output session-bundle.json

# Later: Use saved evidence for comparison
rea compare-artifacts \
  '{"kind":"evidence-file","path":"./baseline-bundle.json"}' \
  '{"kind":"evidence-file","path":"./current-bundle.json"}'
```

**JavaScript Helper:**
```javascript
import { readFileSync, writeFileSync } from 'fs';
import { execSync } from 'child_process';

class EvidenceManager {
  constructor(bundlePath) {
    this.bundlePath = bundlePath;
    this.bundle = this.load();
  }
  
  load() {
    try {
      return JSON.parse(readFileSync(this.bundlePath, 'utf8'));
    } catch {
      return { evidence: [] };
    }
  }
  
  save() {
    writeFileSync(
      this.bundlePath, 
      JSON.stringify(this.bundle, null, 2)
    );
  }
  
  addAnalysis(target, options = {}) {
    const result = execSync(
      `rea analyze ${target} --json`,
      { encoding: 'utf8' }
    );
    const evidence = JSON.parse(result);
    this.bundle.evidence.push({
      timestamp: new Date().toISOString(),
      target,
      evidence
    });
    this.save();
    return evidence.evidence_id;
  }
  
  findByTarget(target) {
    return this.bundle.evidence.filter(e => e.target === target);
  }
}

// Usage
const manager = new EvidenceManager('./project-evidence.json');
const evidenceId = manager.addAnalysis('./dist/app.exe');
console.log('Stored evidence:', evidenceId);
```

### 8.5 Comparison Workflow

**Artifact Comparison Pipeline:**
```bash
#!/bin/bash
set -e

BASE_VERSION=$1
NEW_VERSION=$2
OUTPUT_DIR="./comparison-results"

mkdir -p "$OUTPUT_DIR"

echo "Analyzing baseline..."
rea inspect-artifact "$BASE_VERSION" --json > \
  "$OUTPUT_DIR/baseline.json"

echo "Analyzing new version..."
rea inspect-artifact "$NEW_VERSION" --json > \
  "$OUTPUT_DIR/new.json"

echo "Computing delta..."
rea compare-artifacts \
  "{\"kind\":\"evidence-file\",\"path\":\"$OUTPUT_DIR/baseline.json\"}" \
  "{\"kind\":\"evidence-file\",\"path\":\"$OUTPUT_DIR/new.json\"}" \
  --json > "$OUTPUT_DIR/delta.json"

# Extract summary
jq '{
  modules_added: .delta.modules_added | length,
  modules_removed: .delta.modules_removed | length,
  modules_changed: .delta.modules_changed | length,
  overall_status: .overall
}' "$OUTPUT_DIR/delta.json"
```

### 8.6 Feature Tracing

**MCP Tool Pattern:**
```json
{
  "name": "trace_feature",
  "arguments": {
    "binary": "/path/to/app",
    "references": [
      {
        "type": "string",
        "value": "license_key",
        "containing_function": "validate_license"
      },
      {
        "type": "function",
        "name": "check_registration"
      }
    ],
    "options": {
      "max_depth": 10
    }
  }
}
```

**Response Processing:**
```javascript
function processFeatureTrace(traceEvidence) {
  const { normalized_result } = traceEvidence;
  
  // Group by feature component
  const components = new Map();
  
  for (const node of normalized_result.trace_nodes) {
    const component = node.component || 'unknown';
    if (!components.has(component)) {
      components.set(component, []);
    }
    components.get(component).push(node);
  }
  
  // Generate report
  console.log('Feature Implementation:');
  for (const [component, nodes] of components) {
    console.log(`\n${component}:`);
    for (const node of nodes) {
      console.log(`  - ${node.function.name} (${node.address})`);
      if (node.references.length > 0) {
        console.log(`    References: ${node.references.length}`);
      }
    }
  }
  
  // Report limitations
  if (normalized_result.limitations.length > 0) {
    console.log('\nLimitations:');
    normalized_result.limitations.forEach(l => console.log(`  - ${l}`));
  }
}
```

### 8.7 Provider Selection and Configuration

**Dynamic Provider Selection:**
```javascript
async function analyzeWithBestProvider(binary, func) {
  const providers = ['hopper', 'ghidra', 'ida'];
  
  for (const provider of providers) {
    try {
      const result = execSync(
        `rea analyze-function "${binary}" "${func}" ` +
        `--provider ${provider} --json`,
        { 
          encoding: 'utf8',
          timeout: 60000  // 60s timeout
        }
      );
      
      const evidence = JSON.parse(result);
      return { provider, evidence };
      
    } catch (error) {
      console.warn(`${provider} failed:`, error.message);
      continue;
    }
  }
  
  throw new Error('All providers failed');
}

// Usage with fallback
try {
  const { provider, evidence } = await analyzeWithBestProvider(
    './binary',
    'main'
  );
  console.log(`Analyzed with ${provider}`);
  console.log('Pseudocode lines:', 
    evidence.normalized_result.pseudocode.source.split('\n').length
  );
} catch (error) {
  console.error('Analysis failed:', error);
}
```

### 8.8 Error Handling Pattern

**Robust CLI Wrapper:**
```javascript
class ReaClient {
  constructor(options = {}) {
    this.timeout = options.timeout || 120000;
    this.retries = options.retries || 1;
  }
  
  async call(toolName, args) {
    let lastError;
    
    for (let attempt = 0; attempt <= this.retries; attempt++) {
      try {
        const result = execSync(
          `rea ${toolName} ${this.formatArgs(args)} --json`,
          { 
            encoding: 'utf8',
            timeout: this.timeout
          }
        );
        
        const parsed = JSON.parse(result);
        
        // Check for error response
        if (parsed.isError) {
          const error = JSON.parse(parsed.content).error;
          throw new ReaToolError(error);
        }
        
        return parsed;
        
      } catch (error) {
        lastError = error;
        
        // Check if retryable
        if (error instanceof ReaToolError) {
          if (error.code === 'timeout' && attempt < this.retries) {
            console.warn(`Timeout, retrying (${attempt + 1}/${this.retries})`);
            continue;
          }
          
          // Handle specific recovery hints
          if (error.recovery?.kind === 'inspect_input_contract') {
            throw new Error(
              `Invalid input for ${error.recovery.operation}. ` +
              `Check tool schema: ${error.details}`
            );
          }
        }
        
        throw lastError;
      }
    }
    
    throw lastError;
  }
  
  formatArgs(args) {
    return Object.entries(args)
      .map(([k, v]) => `--${k} ${JSON.stringify(v)}`)
      .join(' ');
  }
}

class ReaToolError extends Error {
  constructor(errorObj) {
    super(errorObj.message);
    this.code = errorObj.code;
    this.details = errorObj.details;
    this.recovery = errorObj.recovery;
    this.remediation = errorObj.remediation;
  }
}
```

---

## 9. Windows Compatibility Notes

### 9.1 Native Windows Support

**Native Addon:**
- Package includes prebuilt `rea-windows-x64.node`
- Located in `native/windows/build/`
- Verified via `verify-windows-native-artifact.mjs`
- Automatically included in npm package

**Shell Compatibility:**
- CLI runs in Git Bash (POSIX sh)
- PowerShell supported for environment management
- Native Windows paths handled correctly
- Forward slashes in paths (Unix-style)

### 9.2 Windows-Specific Features

**Ghidra on Windows:**
- Dedicated Windows P0 support
- Windows-specific fixtures: `verify:ghidra:windows`
- Package verification: `verify:ghidra:windows:package`
- Custom compilation settings

**Windows Binary Analysis:**
- PE/PE+ format support
- PE certificate extraction
- PE import analysis
- PE load configuration
- TLS callback detection

### 9.3 Installation on Windows

**Prerequisites:**
```powershell
# Check Node.js version
node --version  # Should be 22.23.4+ or 24.22.1+

# Install REA
npx rea-agents setup
```

**Path Considerations:**
```powershell
# Use absolute paths
rea analyze "C:\Users\User\Desktop\app.exe" --json

# Or Unix-style
rea analyze "C:/Users/User/Desktop/app.exe" --json
```

**Profile Isolation (PowerShell):**
```powershell
# Set profile for session
$env:CLAUDE_CONFIG_DIR = Join-Path $HOME ".claude-rea"

# Run setup
npx rea-agents setup --client claude_code

# Launch Claude with profile
claude

# Restore original
$env:CLAUDE_CONFIG_DIR = $previousValue
```

### 9.4 Windows Verification Scripts

**Available Tests:**
```bash
npm run verify:windows-native          # Native addon functionality
npm run verify:windows-native:artifact # Package integrity
npm run verify:ghidra:windows         # Ghidra Windows support
npm run verify:package:windows        # Windows packaging
npm run probe:windows-capabilities    # Capability detection
```

### 9.5 Known Windows Considerations

**File Paths:**
- Use absolute paths for reliability
- Both `\` and `/` separators supported
- UNC paths supported

**Process Management:**
- Uses Windows-native process APIs
- Proper cleanup of child processes
- Handle management via native addon

**Permissions:**
- No elevation required for analysis
- Read-only access to target files
- Writes only to specified output locations

---

## 10. Integration Checklist for VERONIKA

### 10.1 Prerequisites

- [ ] Node.js 22.23.4+ installed
- [ ] Windows 11 environment configured
- [ ] Git Bash or PowerShell available
- [ ] Network access for initial setup
- [ ] Write permissions for config directories

### 10.2 Installation Steps

```bash
# 1. Install REA globally or via npx
npm install --global rea-agents

# 2. Verify installation
rea --version

# 3. Run setup for Claude Code integration
rea setup --client claude_code --dry-run

# 4. Review and approve setup
rea setup --client claude_code

# 5. Verify health
rea doctor --client claude_code --skill --json
```

### 10.3 Configuration Decisions

**Provider Selection:**
- [ ] Hopper (auto-install via setup) - macOS focused
- [ ] Ghidra (bring your own) - Multi-platform
- [ ] IDA (bring your own) - Commercial
- [ ] JavaScript-only (no native provider needed)

**Integration Mode:**
- [ ] MCP server for agent interaction ✅ Recommended
- [ ] CLI for scripted workflows
- [ ] Both (full capability)

**Profile Strategy:**
- [ ] Global REA registration (all projects)
- [ ] Isolated profile for VERONIKA only

### 10.4 Testing Integration

```bash
# Test JavaScript analysis (no provider needed)
npx -y rea-agents@latest analyze-javascript-application \
  /path/to/test/app --json

# Test MCP server
rea mcp  # Should start without errors

# Test agent communication
# In Claude Code session:
# "Use REA to analyze this application: /path/to/app"
```

### 10.5 VERONIKA-Specific Considerations

**AI Entity Manager Integration:**
- REA can analyze AI model binaries
- Provider configuration stored in `app/config.py`
- Can compare model versions for changes
- Evidence trails for security audits

**Model Scout Integration:**
- REA can inspect native ML libraries
- Compare inference engine implementations
- Trace model loading and initialization
- Verify security of model handling code

**Persona Manager Analysis:**
- Analyze persona storage formats
- Compare persona implementations
- Trace persona switching logic
- Verify persona isolation

**Security Auditing:**
- REA aligns with `docs/SECURITY.md` requirements
- Local-only analysis (no data exfiltration)
- Evidence-based security reviews
- Comparison across versions

### 10.6 Performance Expectations

**First Analysis:**
- Provider startup: 5-30s (Ghidra cold start)
- JavaScript analysis: 1-10s (depends on app size)
- Function analysis: 2-60s (depends on complexity)

**Cached Analysis:**
- Identical inputs reuse validated snapshots
- Near-instant for repeated queries
- Evidence retention across session

**Memory Usage:**
- Base REA: ~50-200 MB
- With Ghidra: +500 MB - 2 GB
- Evidence bundles: variable (10 MB - 1 GB+)

### 10.7 Troubleshooting

**Common Issues:**

1. **Provider not found:**
   ```bash
   rea doctor --json  # Check provider status
   rea setup --install-hopper  # Auto-install Hopper
   ```

2. **MCP server won't start:**
   ```bash
   rea config:print  # Verify configuration
   # Check ~/.claude.json registration
   ```

3. **Analysis timeout:**
   ```bash
   # Increase timeout via environment
   REA_MCP_MAX_RESPONSE_BYTES=10485760 rea mcp
   ```

4. **Permission denied:**
   ```bash
   # Verify file permissions
   # Check that target is readable
   # Ensure output directory is writable
   ```

**Debug Mode:**
```bash
# Enable verbose logging (if supported)
NODE_DEBUG=rea rea analyze target --json

# Check process state
rea doctor --json | jq '.provider_status'
```

---

## 11. Conclusion

REA provides a comprehensive, production-ready reverse-engineering toolkit with excellent Windows support and deep integration capabilities for AI agents. Its evidence-based approach, local-only execution model, and extensive format support make it ideal for security analysis, feature understanding, and competitive research.

**Key Advantages for VERONIKA:**
1. **Privacy-First:** All analysis runs locally, no cloud dependencies
2. **Windows Native:** First-class Windows support with native addon
3. **Agent-Ready:** MCP server enables seamless Claude Code integration
4. **Evidence-Based:** Structured, verifiable results with provenance
5. **Comprehensive:** 40+ target types including native, web, mobile, firmware

**Recommended Next Steps:**
1. Install REA and run setup with dry-run
2. Test JavaScript analysis on VERONIKA codebase
3. Configure Ghidra for native binary analysis
4. Integrate MCP server with Claude Code profile
5. Document VERONIKA-specific analysis workflows

**Documentation References:**
- Main docs: https://rea.tools/
- GitHub: https://github.com/morluto/rea
- Installation: `/docs/installation.md`
- MCP contracts: `/docs/mcp-contracts.md`
- CLI usage: `/docs/cli.md`

---

## Appendix A: Dependencies

**Core Dependencies (39):**
- @babel/parser, @babel/types - JavaScript parsing
- @modelcontextprotocol/client, server - MCP implementation
- @electron/asar - Electron app support
- playwright-core - Browser automation
- zod - Schema validation
- ws - WebSocket support
- 33+ additional specialized libraries

**Optional Dependencies:**
- frida@17.23.2 - Runtime instrumentation

**Dev Dependencies (24):**
- TypeScript 7.0.2 (main), 6.0.3, 5.9.3 (termux)
- vitest - Testing framework
- turbo - Monorepo orchestration
- oxlint, oxfmt - Linting and formatting

## Appendix B: npm Scripts Reference

**Primary Commands:**
- `npm run build` - Build runtime and skills
- `npm run test` - Run test suite with build
- `npm run check` - Full validation (typecheck, lint, format)
- `npm run check:pr` - Complete PR gate

**Verification Commands:**
- `npm run verify:hopper` - Hopper integration
- `npm run verify:ghidra` - Ghidra integration
- `npm run verify:windows-native` - Windows functionality
- `npm run verify:browser` - Browser observation
- `npm run verify:android` - Android analysis

**Specialized:**
- 100+ verification scripts for specific features
- Provider-specific test suites
- Architecture-specific validations
- Platform-specific checks

## Appendix C: File Locations

**Configuration:**
- User config: `~/.claude.json` (Claude Code)
- REA skills: `~/.claude/skills/reverse-engineer-anything/`
- Plugin config: `.claude-plugin/plugin.json`

**Evidence:**
- Session bundles: User-specified locations
- Temporary files: System temp directory
- Cache: `.cache/mcp-tool-catalog.json`

**Windows Native:**
- Addon: `native/windows/build/rea-windows-x64.node`
- Manifest: `native/windows/build/manifest.json`

---

**End of Audit**
