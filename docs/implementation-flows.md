# Implementation Flows

Mermaid diagrams in this document target Mermaid `v11.14.0`.

## Current Phase 0 Repository Flow

```mermaid
flowchart TD
    A["Workspace root"] --> B["backend"]
    A --> C["mobile"]
    A --> D["frontend"]
    A --> E["docs"]

    B --> F["app"]
    B --> G["storage"]
    B --> H["pyproject.toml"]
    B --> I["uv.lock"]

    F --> J["api"]
    F --> K["core"]
    F --> L["db"]
    F --> M["models"]
    F --> N["schemas"]
    F --> O["services"]
    F --> P["workers"]
    F --> Q["main.py"]

    G --> R["raw-scans"]
    G --> S["frames"]
    G --> T["models"]
    G --> U["designs"]
    G --> V["exports"]
```

## Current Backend Startup Flow

```mermaid
flowchart TD
    A["Start uvicorn app.main:app"] --> B["Load Settings"]
    B --> C["Resolve backend root"]
    C --> D["Resolve storage root"]
    C --> E["Resolve SQLite database URL"]
    D --> F["FastAPI lifespan starts"]
    F --> G["Create storage directories"]
    G --> H["API ready"]
    H --> I["GET /health"]
    I --> J["Return status ok"]
```

## Current Local Development Flow

```mermaid
flowchart LR
    A["Developer"] --> B["Install or bootstrap uv"]
    B --> C["Run uv sync in backend"]
    C --> D["Create local .venv"]
    C --> E["Create uv.lock"]
    D --> F["Run uvicorn"]
    F --> G["Call /health"]
    G --> H["Confirm backend is alive"]
```

## Current Health Request Sequence

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant API as FastAPI App
    participant Settings as Settings
    participant Storage as Local Storage

    Dev->>API: GET /health
    API->>Settings: Read app name and environment
    API-->>Dev: 200 status ok
    Note over API,Storage: Storage folders are initialized during app startup.
```

## Target MVP Product Flow

This is the full project flow the repository is being prepared for. Only Phase 0 is implemented now.

```mermaid
flowchart TD
    A["Flutter Mobile Scanner"] --> B["Record guided shoe video"]
    B --> C["Collect shoe metadata"]
    C --> D["Upload video and metadata"]
    D --> E["FastAPI scan session API"]
    E --> F["Store raw scan files"]
    F --> G["SQLite scan status tracking"]
    G --> H["Automatic processing job"]
    H --> I["Extract frames with FFmpeg"]
    I --> J["COLMAP and OpenMVS ready pipeline"]
    J --> K["Mesh cleanup"]
    K --> L["UV unwrap"]
    L --> M["Texture bake"]
    M --> N["Export GLB and OBJ assets"]
    N --> O["Vite React web editor"]
    O --> P["Load scanned GLB"]
    P --> Q["Apply color stickers and text"]
    Q --> R["Save design_config.json separately"]
    R --> S["Generate visual design package"]
    S --> T["ZIP with GLB OBJ MTL texture previews notes"]
```

## Planned Auth And Demo Login Flow

```mermaid
flowchart TD
    A["User opens app"] --> B{"Has account session"}
    B -->|"Yes"| C["Use authenticated user"]
    B -->|"No"| D["Show login screen"]
    D --> E["Login or register"]
    D --> F["Skip login for demo"]
    F --> G["Use fixed demo user"]
    E --> H["Issue authorized API session"]
    G --> H
    H --> I["Access scan design and export APIs"]
```

## Phased Implementation Roadmap

```mermaid
flowchart TD
    P0["Phase 0 Repository and FastAPI foundation"] --> P1["Phase 1 Backend scan session API"]
    P1 --> P2["Phase 2 Flutter mobile scanner"]
    P1 --> P3["Phase 3 Frame extraction and mock reconstruction"]
    P3 --> P4["Phase 4 COLMAP and OpenMVS hooks"]
    P3 --> P5["Phase 5 Vite React 3D viewer"]
    P5 --> P6["Phase 6 Web decoration editor"]
    P6 --> P7["Phase 7 Visual design package export"]
    P7 --> P8["Phase 8 End to end demo script"]
```
