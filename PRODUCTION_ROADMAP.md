# ar-ai-exe Monorepo - Production Readiness Roadmap

**Document Version:** 1.0  
**Created:** July 8, 2026  
**Status:** Pre-Production Review  

---

## Executive Summary

| Platform | Current Score | Target Score | Verdict |
|----------|--------------|--------------|---------|
| **Backend** | 7.5/10 | 9/10 | ✅ Ready with monitoring |
| **Frontend** | 5.5/10 | 9/10 | ❌ Not Ready |
| **Mobile** | 4.0/10 | 8/10 | ❌ Early Beta |
| **Desktop** | 4.5/10 | 8/10 | ❌ Early Beta |
| **Overall** | **5.5/10** | **9/10** | - |

**Verdict:** Backend có thể triển khai. Frontend, Mobile, và Desktop cần thêm work trước khi production.

---

## Platform Overview

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────┐
│                        ar-ai-exe Monorepo                       │
├─────────────┬─────────────┬─────────────┬──────────────────────┤
│   Mobile    │   Frontend  │   Desktop   │       Backend         │
│  (Flutter)  │   (React)   │   (Tauri)   │      (FastAPI)       │
├─────────────┼─────────────┼─────────────┼──────────────────────┤
│    MVP      │   MVP       │    Beta     │       Stable          │
│   v0.1.0   │   v0.1.0    │   v0.1.0    │       v0.1.0         │
└─────────────┴─────────────┴─────────────┴──────────────────────┘
```

---

## Phase 1: Critical Security Fixes (Week 1)

### 1.1 Backend Security

#### [CRITICAL] Rate Limiting on Demo Auth
**File:** `backend/app/api/auth.py`
**Priority:** P0
**Effort:** 1 day

**Mô tả:** Demo auth endpoint cho phép tạo user vô hạn.

**Implementation:**
```python
# backend/app/api/auth.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/demo-login")
@limiter.limit("5/minute")  # Giới hạn 5 lần/phút
async def demo_login(request: Request):
    # existing implementation
```

**Acceptance Criteria:**
- [ ] Demo login bị rate limit 5 requests/phút
- [ ] Trả về 429 khi exceed limit
- [ ] Logs khi rate limit triggered

#### [HIGH] CORS Production Configuration
**File:** `backend/app/main.py`
**Priority:** P1
**Effort:** 0.5 day

**Mô tả:** CORS hiện tại cho phép tất cả localhost ports - cần tighten cho production.

**Implementation:**
```python
# backend/app/main.py
ALLOWED_ORIGINS = [
    "https://kusshoes.vn",
    "https://www.kusshoes.vn",
    "https://staging.kusshoes.vn",
    "http://localhost:5173",  # Dev only
    "http://localhost:1420",  # Desktop dev
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

### 1.2 Frontend Security

#### [CRITICAL] JWT Token Security Enhancement
**File:** `frontend/src/api/client.ts`
**Priority:** P0
**Effort:** 2 days

**Mô tả:** JWT token trong localStorage dễ bị XSS attack.

**Solution: Use httpOnly Cookies for Refresh Token**
```typescript
// frontend/src/api/client.ts
class ApiClient {
  private baseUrl: string;
  
  constructor() {
    this.baseUrl = import.meta.env.VITE_API_BASE_URL;
  }

  async login(email: string, password: string) {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      credentials: 'include',  // Quan trọng: nhận cookies
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      throw new ApiError(await response.json());
    }
    
    // Token sẽ được set trong httpOnly cookie bởi backend
    const data = await response.json();
    this.setAccessToken(data.access_token); // Chỉ access token vào memory
    return data;
  }

  private accessToken: string | null = null;

  setAccessToken(token: string) {
    this.accessToken = token;
  }

  async request<T>(endpoint: string, options: RequestInit = {}) {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      credentials: 'include',
      headers,
    });

    // Auto-refresh khi 401
    if (response.status === 401 && this.accessToken) {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        return fetch(`${this.baseUrl}${endpoint}`, { ...options, credentials: 'include', headers });
      }
    }

    return response;
  }

  private async refreshToken(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      
      if (response.ok) {
        const data = await response.json();
        this.setAccessToken(data.access_token);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  logout() {
    this.accessToken = null;
    return fetch(`${this.baseUrl}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  }
}
```

**Acceptance Criteria:**
- [ ] Refresh token chỉ trong httpOnly cookie
- [ ] Access token trong memory (không localStorage)
- [ ] Auto-refresh flow hoạt động
- [ ] Logout xóa cookies server-side

### 1.3 Mobile Security

#### [CRITICAL] Remove Hardcoded Backend URL
**File:** `mobile/lib/services/backend_api.dart`
**Priority:** P0
**Effort:** 0.5 day

**Mô tả:** Hardcoded IP `172.16.1.232` trong backend_api.dart.

**Implementation:**
```dart
// mobile/lib/services/backend_api.dart
class BackendApi {
  // Thay vì hardcode:
  // static const String _baseUrl = 'http://172.16.1.232:8000';
  
  // Sử dụng environment config:
  static String get baseUrl {
    const configuredUrl = String.fromEnvironment(
      'BACKEND_URL',
      defaultValue: 'https://api.kusshoes.vn',
    );
    return configuredUrl;
  }
  
  // Hoặc sử dụng shared_preferences để user có thể thay đổi:
  static Future<String> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('backend_url') ?? 'https://api.kusshoes.vn';
  }
}
```

**Acceptance Criteria:**
- [ ] Không có hardcoded IP trong source code
- [ ] Backend URL từ environment/config
- [ ] Hỗ trợ staging environment

#### [MEDIUM] Certificate Pinning
**File:** `mobile/lib/services/backend_api.dart`
**Priority:** P2
**Effort:** 1 day

**Mô tả:** Thêm SSL certificate pinning cho production.

---

## Phase 2: Error Handling & Stability (Week 1-2)

### 2.1 Frontend Error Handling

#### [CRITICAL] Add Global Error Boundary
**File:** `frontend/src/main.tsx`
**Priority:** P0
**Effort:** 1 day

**Mô tả:** App.tsx (1717 dòng) crash sẽ crash toàn bộ app.

**Implementation:**
```tsx
// frontend/src/main.tsx
import { ErrorBoundary } from './components/Layout/ErrorBoundary';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
```

**Enhanced ErrorBoundary:**
```tsx
// frontend/src/components/Layout/ErrorBoundary.tsx
import { Component, ReactNode } from 'react';
import { Button } from './ui/Button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Unhandled error:', error, errorInfo);
    // TODO: Send to error tracking service
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="error-fallback">
          <h1>Something went wrong</h1>
          <p>{this.state.error?.message}</p>
          <Button onClick={() => window.location.reload()}>
            Reload App
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

**Acceptance Criteria:**
- [ ] Unhandled errors hiển thị fallback UI
- [ ] Error được log (console + tracking service)
- [ ] User có thể reload app

#### [HIGH] Refactor App.tsx Monolith
**File:** `frontend/src/App.tsx`
**Priority:** P1
**Effort:** 5 days

**Mô tả:** 1717 dòng là quá lớn, cần tách thành feature modules.

**New Structure:**
```
frontend/src/
├── features/
│   ├── auth/
│   │   ├── components/
│   │   │   ├── AuthPanel.tsx
│   │   │   └── AuthForm.tsx
│   │   ├── hooks/
│   │   │   └── useAuth.ts
│   │   └── index.ts
│   ├── scan/
│   │   ├── components/
│   │   │   ├── ScanLoader.tsx
│   │   │   └── ScanStatus.tsx
│   │   ├── hooks/
│   │   │   └── useScan.ts
│   │   └── index.ts
│   ├── editor/
│   │   ├── components/
│   │   │   ├── EditorLayout.tsx
│   │   │   ├── Toolbar.tsx
│   │   │   └── StatusBar.tsx
│   │   ├── hooks/
│   │   │   └── useEditor.ts
│   │   └── index.ts
│   └── desktop/
│       ├── components/
│       │   ├── DesktopLauncher.tsx
│       │   └── RuntimePanel.tsx
│       └── index.ts
├── shared/
│   ├── components/
│   │   ├── ErrorBoundary.tsx
│   │   └── LoadingSpinner.tsx
│   └── hooks/
│       └── useAsync.ts
├── App.tsx  # Chỉ routing và layout
└── main.tsx
```

**Migration Plan:**
1. Tạo `features/auth/` với AuthPanel, useAuth hook
2. Tạo `features/scan/` với ScanLoader, useScan hook
3. Tạo `features/editor/` với EditorPanels, useEditor hook
4. Tạo `features/desktop/` với DesktopLauncher, RuntimePanel
5. Simplify App.tsx thành router + layout

**Acceptance Criteria:**
- [ ] App.tsx giảm xuống < 200 dòng
- [ ] Mỗi feature có index.ts exports
- [ ] Hooks được share giữa features
- [ ] Import paths sử dụng absolute imports

### 2.2 Backend Error Handling

#### [HIGH] Worker Failure Notifications
**File:** `backend/app/workers/rq_worker.py`
**Priority:** P1
**Effort:** 1 day

**Mô tả:** Workers có thể fail silent - cần thông báo.

**Implementation:**
```python
# backend/app/workers/rq_worker.py
import sentry_sdk
from loguru import logger

def notify_failure(job, *args, **kwargs):
    """Called when job fails"""
    error_message = str(job.exc_info[1]) if job.exc_info else "Unknown error"
    
    logger.error(
        f"Job failed: {job.id}",
        extra={
            "job_id": job.id,
            "function": job.func_name,
            "error": error_message,
        }
    )
    
    # Send to monitoring
    sentry_sdk.capture_message(
        f"RQ Job Failed: {job.func_name}",
        extras={
            "job_id": job.id,
            "error": error_message,
        }
    )
    
    # Optional: Send to Slack/Discord
    # send_alert_to_oncall(f"Job {job.id} failed: {error_message}")

@worker.got_job
def on_job_success(job, *args, **kwargs):
    logger.info(f"Job completed: {job.id}", extra={"duration": job.ended_at - job.started_at})
```

### 2.3 Mobile Error Handling

#### [MEDIUM] Error Widget for Flutter
**File:** `mobile/lib/app/app_shell.dart`
**Priority:** P2
**Effort:** 1 day

**Mô tả:** Thêm error handling cho Flutter app.

**Implementation:**
```dart
// mobile/lib/widgets/error_widget.dart
class AppErrorWidget extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;
  
  const AppErrorWidget({
    super.key,
    required this.message,
    this.onRetry,
  });
  
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: onRetry,
                child: const Text('Retry'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// Wrap screens with error handling
class SafeBuilder<T> extends FutureBuilder<T> {
  SafeBuilder({
    required Future<T> future,
    required Widget Function(BuildContext, T) builder,
    Widget? errorWidget,
  }) : super(
          future: future,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return AppErrorWidget(
                message: snapshot.error.toString(),
                onRetry: () {}, // Rebuild by invalidating
              );
            }
            return builder(context, snapshot.data as T);
          },
        );
}
```

### 2.4 Desktop Error Handling

#### [MEDIUM] Crash Reporting
**File:** `desktop/src-tauri/src/main.rs`
**Priority:** P2
**Effort:** 1 day

**Mô tả:** Desktop app cần crash reporting.

**Implementation:**
```rust
// desktop/src-tauri/src/main.rs
use std::panic;

fn main() {
    // Set up panic hook for crash logging
    panic::set_hook(Box::new(|panic_info| {
        let message = if let Some(s) = panic_info.payload().downcast_ref::<&str>() {
            s.to_string()
        } else if let Some(s) = panic_info.payload().downcast_ref::<String>() {
            s.clone()
        } else {
            "Unknown panic".to_string()
        };
        
        let location = panic_info.location()
            .map(|l| format!("{}:{}:{}", l.file(), l.line(), l.column()))
            .unwrap_or_else(|| "unknown".to_string());
        
        // Write to crash log
        let crash_log = format!(
            "[{}] PANIC at {}: {}\n",
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
            location,
            message
        );
        
        if let Ok(mut file) = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open("crash.log")
        {
            use std::io::Write;
            let _ = file.write_all(crash_log.as_bytes());
        }
        
        // TODO: Upload to crash reporting service
        eprintln!("{}", crash_log);
    }));
    
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

---

## Phase 3: Testing (Week 2-3)

### 3.1 Backend Tests

#### [HIGH] Increase Coverage
**Files:** `backend/tests/`
**Priority:** P1
**Effort:** 5 days

**Current Status:**
- ✅ Unit tests cho decal_baker, mesh_cleanup, model_imports
- ✅ Integration tests cho editor_integration
- ❌ Missing: API integration tests, security tests

**Target Coverage:**
```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

**Priority Test Cases:**
| Test | Priority | Description |
|------|----------|-------------|
| Auth: Login/Register/Refresh | P0 | Full auth flow |
| Auth: Rate Limiting | P0 | Demo login limits |
| Design: Create/Update/Delete | P1 | CRUD operations |
| Design: Asset Upload | P1 | File validation |
| Editor: Permissions | P0 | canEdit, canBake, canExport |
| Reconstruction: Status Polling | P1 | Status transitions |
| Export: Package Creation | P1 | ZIP generation |

### 3.2 Frontend Tests

#### [HIGH] Vitest Setup and Basic Tests
**Files:** `frontend/src/**/*.test.ts`, `frontend/src/**/*.test.tsx`
**Priority:** P1
**Effort:** 3 days

**Setup:**
```bash
cd frontend
npm install -D vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom
```

**Priority Tests:**
```typescript
// frontend/src/api/client.test.ts
describe('ApiClient', () => {
  describe('login', () => {
    it('should store access token in memory', async () => {
      // Test token handling
    });
    
    it('should reject invalid credentials', async () => {
      // Test error handling
    });
  });
  
  describe('refreshToken', () => {
    it('should auto-refresh on 401', async () => {
      // Test auto-refresh
    });
  });
});

// frontend/src/utils/editorMessages.test.ts
describe('editorMessages', () => {
  describe('friendlyInlineMessage', () => {
    it('should truncate long error messages', () => {
      // Test message formatting
    });
  });
});
```

#### [MEDIUM] Playwright E2E Tests
**Files:** `frontend/e2e/`
**Priority:** P2
**Effort:** 5 days

**Critical Flows:**
1. User can login/logout
2. User can load scan by ID
3. User can create design with stickers
4. User can save and export design
5. Editor permissions are enforced

### 3.3 Mobile Tests

#### [MEDIUM] Flutter Widget Tests
**Files:** `mobile/test/`
**Priority:** P2
**Effort:** 3 days

**Setup:**
```bash
cd mobile
flutter test
```

**Priority Tests:**
1. `ScanHomeScreen` - scan button tap
2. `CameraScanScreen` - camera permission handling
3. `UploadProgressScreen` - progress display
4. `BackendApi` - auth flow (mocked)

### 3.4 Desktop Tests

#### [LOW] Rust Unit Tests
**Files:** `desktop/src-tauri/src/**/*.rs`
**Priority:** P3
**Effort:** 2 days

**Setup:**
```rust
#[cfg(test)]
mod tests {
    #[test]
    fn test_backend_url_parsing() {
        // Test URL parsing logic
    }
    
    #[test]
    fn test_port_scanning() {
        // Test port detection
    }
}
```

Run with: `cargo test`

---

## Phase 4: CI/CD (Week 3-4)

### 4.1 Backend CI/CD

#### [HIGH] Add Docker Build to CI
**File:** `.github/workflows/backend-ci.yml`
**Priority:** P1
**Effort:** 1 day

**Addition:**
```yaml
- name: Build Docker Image
  run: |
    docker build -t kusshoes-backend:${{ github.sha }} -f backend/Dockerfile backend/
    docker tag kusshoes-backend:${{ github.sha }} kusshoes-backend:latest

- name: Push to Registry
  if: github.ref == 'refs/heads/main'
  run: |
    echo ${{ secrets.REGISTRY_TOKEN }} | docker login -u ci --password-stdin registry.kusshoes.vn
    docker push registry.kusshoes.vn/kusshoes-backend:${{ github.sha }}
    docker push registry.kusshoes.vn/kusshoes-backend:latest
```

### 4.2 Frontend CI/CD

#### [HIGH] Add Tests to CI
**File:** `.github/workflows/frontend-ci.yml`
**Priority:** P1
**Effort:** 0.5 day

**Addition:**
```yaml
- name: Run Tests
  run: npm run test -- --run

- name: Run E2E Tests
  if: github.ref == 'refs/heads/main'
  run: npx playwright test
```

### 4.3 Mobile CI/CD

#### [HIGH] Build Verification
**File:** `.github/workflows/mobile-ci.yml`
**Priority:** P1
**Effort:** 1 day

**Addition:**
```yaml
- name: Build iOS
  run: flutter build ios --simulator --no-codesign
  env:
    FLUTTER_VERSION: stable

- name: Build Android APK
  run: flutter build apk --debug
  env:
    FLUTTER_VERSION: stable

- name: Upload Build Artifacts
  uses: actions/upload-artifact@v4
  with:
    name: mobile-builds
    path: |
      build/ios/iphonesimulator/Runner.app
      build/app/outputs/flutter-apk/app-debug.apk
```

### 4.4 Desktop CI/CD

#### [HIGH] Add Tauri CI
**Files:** `.github/workflows/desktop-ci.yml`
**Priority:** P1
**Effort:** 2 days

**New File:**
```yaml
name: Desktop CI

on:
  push:
    paths:
      - 'desktop/**'
      - 'frontend/**'
  pull_request:
    paths:
      - 'desktop/**'
      - 'frontend/**'

jobs:
  build:
    strategy:
      matrix:
        platform: [macos-latest, ubuntu-22.04, windows-latest]
    
    runs-on: ${{ matrix.platform }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install Frontend Dependencies
        run: npm ci
        working-directory: frontend
        
      - name: Build Frontend
        run: npm run build:desktop
        working-directory: frontend
        
      - name: Setup Rust
        uses: dtolnay/rust-action@stable
        with:
          components: rustfmt, clippy
          
      - name: Install Tauri CLI
        run: cargo install tauri-cli
        working-directory: desktop
        
      - name: Build Tauri App
        run: npm run build
        working-directory: desktop
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Upload Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: tauri-app-${{ matrix.platform }}
          path: desktop/src-tauri/target/release/bundle/**
```

---

## Phase 5: Monitoring & Observability (Week 4)

### 5.1 Backend Monitoring

#### [HIGH] Structured Logging
**File:** `backend/app/main.py`
**Priority:** P1
**Effort:** 1 day

**Implementation:**
```python
# backend/app/main.py
import json
import uuid
from contextvars import ContextVar
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)
        
        with logger.contextualize(request_id=request_id):
            logger.info(
                "Request started",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client": request.client.host if request.client else None,
                }
            )
            
            response = await call_next(request)
            
            logger.info(
                "Request completed",
                extra={
                    "status_code": response.status_code,
                    "duration_ms": 0,  # Calculate actual duration
                }
            )
            
            response.headers["X-Request-ID"] = request_id
            return response
```

#### [MEDIUM] Health Check Enhancement
**File:** `backend/app/api/system.py`
**Priority:** P2
**Effort:** 0.5 day

**Enhancement:**
```python
@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Enhanced health check with dependency status"""
    checks = {
        "database": await check_db(db),
        "redis": await check_redis(),
        "storage": await check_storage(),
        "reconstruction_toolchain": await check_toolchain(),
    }
    
    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "version": VERSION,
        "checks": checks,
    }
```

### 5.2 Frontend Monitoring

#### [MEDIUM] Sentry Integration
**File:** `frontend/src/main.tsx`
**Priority:** P2
**Effort:** 0.5 day

```tsx
import * as Sentry from '@sentry/react';

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.MODE,
  integrations: [
    Sentry.browserTracingIntegration(),
  ],
  tracesSampleRate: 0.1,
  
  // Ignore common noise
  ignoreErrors: [
    'ResizeObserver loop completed with undelivered notifications',
  ],
});
```

### 5.3 Mobile Monitoring

#### [MEDIUM] Firebase Crashlytics
**File:** `mobile/lib/main.dart`
**Priority:** P2
**Effort:** 0.5 day

```dart
import 'package:firebase_crashlytics/firebase_crashlytics.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Crashlytics
  FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterError;
  
  runApp(const MyApp());
}
```

---

## Phase 6: Mobile-Specific (Week 4-5)

### 6.1 Mobile App Improvements

#### [HIGH] Refactor app_shell.dart
**File:** `mobile/lib/app/app_shell.dart`
**Priority:** P1
**Effort:** 3 days

**Mô tả:** 911 dòng cần tách thành modules.

**New Structure:**
```
mobile/lib/
├── features/
│   ├── auth/
│   │   └── auth_screen.dart
│   ├── scan/
│   │   ├── scan_home_screen.dart
│   │   ├── camera_scan_screen.dart
│   │   └── scan_result_screen.dart
│   └── upload/
│       └── upload_progress_screen.dart
├── widgets/
│   ├── scan_hero_card.dart
│   ├── scan_guide_overlay.dart
│   └── scan_status_chips.dart
└── app/
    ├── app_shell.dart  # Chỉ routing
    └── app_router.dart
```

#### [MEDIUM] Add Retry Logic
**File:** `mobile/lib/services/backend_api.dart`
**Priority:** P2
**Effort:** 1 day

**Implementation:**
```dart
class RetryInterceptor extends Interceptor {
  final Dio dio;
  
  RetryInterceptor(this.dio);
  
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (_shouldRetry(err)) {
      try {
        final response = await _retry(err.requestOptions);
        handler.resolve(response);
        return;
      } catch (e) {
        // Retry failed
      }
    }
    handler.next(err);
  }
  
  bool _shouldRetry(DioException err) {
    return err.type == DioExceptionType.connectionTimeout ||
           err.type == DioExceptionType.receiveTimeout ||
           (err.response?.statusCode == 503);
  }
  
  Future<Response> _retry(RequestOptions options) async {
    return dio.fetch(options);
  }
}
```

---

## Phase 7: Desktop-Specific (Week 4-5)

### 7.1 Desktop App Improvements

#### [HIGH] Auto-Update System
**File:** `desktop/src-tauri/tauri.conf.json`
**Priority:** P1
**Effort:** 2 days

**Implementation:**
```json
// desktop/src-tauri/tauri.conf.json
{
  "plugins": {
    "updater": {
      "endpoints": [
        "https://releases.kusshoes.vn/desktop/{{target}}/{{arch}}/{{current_version}}"
      ],
      "pubkey": "YOUR_ED25519_PUBLIC_KEY"
    }
  }
}
```

#### [MEDIUM] Installer Verification
**Files:** `desktop/scripts/`
**Priority:** P2
**Effort:** 1 day

**CI Verification:**
```bash
# Verify Windows installer
signtool verify /pa desktop/src-tauri/target/release/bundle/nsis/*.exe

# Verify macOS app
codesign -dvvv desktop/src-tauri/target/release/bundle/macos/*.app

# Verify Linux deb
dpkg-sig --verify desktop/src-tauri/target/release/bundle/deb/*.deb
```

---

## Implementation Timeline

```
Week 1: Critical Security Fixes
├── Backend: Rate Limiting (1 day)
├── Backend: CORS Configuration (0.5 day)
├── Frontend: Token Security (2 days)
└── Mobile: Remove Hardcoded URL (0.5 day)

Week 2: Error Handling & Stability  
├── Frontend: Error Boundary (1 day)
├── Frontend: App.tsx Refactor (5 days)
├── Backend: Worker Notifications (1 day)
├── Mobile: Error Widget (1 day)
└── Desktop: Crash Reporting (1 day)

Week 3: Testing
├── Backend: Increase Coverage (5 days)
├── Frontend: Vitest + Tests (3 days)
├── Frontend: Playwright E2E (5 days) - parallel
├── Mobile: Widget Tests (3 days) - parallel
└── Desktop: Rust Tests (2 days) - parallel

Week 4: CI/CD & Monitoring
├── Backend CI: Docker Build (1 day)
├── Frontend CI: Add Tests (0.5 day)
├── Mobile CI: Build Verification (1 day)
├── Desktop CI: Tauri CI Setup (2 days)
├── Backend: Structured Logging (1 day)
├── Frontend: Sentry (0.5 day)
└── Mobile: Crashlytics (0.5 day)

Week 5: Platform-Specific
├── Mobile: Refactor app_shell.dart (3 days)
├── Mobile: Retry Logic (1 day)
├── Desktop: Auto-Update (2 days)
└── Desktop: Installer Verification (1 day)

Total: ~5 weeks
```

---

## Definition of Done

### Backend - Production Ready
- [ ] Rate limiting on all public endpoints
- [ ] CORS restricted to allowed origins
- [ ] Worker failure notifications
- [ ] Structured logging with request IDs
- [ ] Test coverage > 70%
- [ ] Health check với dependency status
- [ ] Docker image builds successfully

### Frontend - Production Ready
- [ ] Token security (httpOnly cookies)
- [ ] Global error boundary
- [ ] App.tsx refactored (< 200 lines)
- [ ] Unit tests cho critical paths
- [ ] E2E tests cho user flows
- [ ] Sentry integration
- [ ] Build size < 500KB gzipped

### Mobile - Beta
- [ ] No hardcoded URLs (see [mobile-backend-contract.md](./docs/mobile-backend-contract.md))
- [ ] Error widget for all screens
- [ ] Retry logic for network failures
- [ ] Crashlytics integration
- [ ] Widget tests cho critical flows
- [ ] CI builds iOS/Android successfully

### Desktop - Beta
- [ ] Crash reporting
- [ ] Tauri CI/CD pipeline
- [ ] Auto-update system
- [ ] Installer signing/verification
- [ ] Rust tests

---

## Appendix: Key File References

### Backend
```
backend/
├── app/
│   ├── api/
│   │   ├── auth.py          # Auth + rate limiting
│   │   ├── system.py         # Health checks
│   │   ├── designs.py        # Design CRUD
│   │   ├── projects.py      # Project management
│   │   └── scan_sessions.py  # Scan workflow
│   ├── services/
│   │   ├── decal_baker.py   # Decal baking (Blender)
│   │   ├── mesh_cleanup.py   # Mesh processing
│   │   └── model_imports.py  # Model import
│   ├── workers/
│   │   ├── rq_worker.py      # Job queue worker
│   │   └── reconstruction_worker.py
│   └── main.py               # FastAPI app
├── tests/
│   ├── test_decal_baker.py
│   ├── test_mesh_cleanup.py
│   └── test_editor_integration.py
├── Dockerfile
├── Dockerfile.dev
└── pyproject.toml
```

### Frontend
```
frontend/
├── src/
│   ├── App.tsx              # 1717 lines - TO SPLIT
│   ├── api/
│   │   ├── client.ts        # API client
│   │   └── editorClient.ts  # Editor API
│   ├── components/
│   │   ├── Editor/          # Editor components
│   │   ├── ModelViewer/      # 3D viewer
│   │   └── Layout/          # Layout + ErrorBoundary
│   └── hooks/
│       └── useEditorContext.ts
├── package.json
├── vite.config.ts
└── Dockerfile
```

### Mobile
```
mobile/
├── lib/
│   ├── app/
│   │   ├── app_shell.dart   # 911 lines - TO REFACTOR
│   │   └── app_theme.dart
│   ├── screens/
│   │   ├── auth_screen.dart
│   │   ├── camera_scan_screen.dart
│   │   ├── scan_home_screen.dart
│   │   └── scan_result_screen.dart
│   ├── services/
│   │   └── backend_api.dart  # Hardcoded URL - TO FIX
│   └── widgets/
│       ├── scan_hero_card.dart
│       └── scan_guide_overlay.dart
├── pubspec.yaml
└── plan.md
```

### Desktop
```
desktop/
├── src-tauri/
│   ├── src/
│   │   └── main.rs          # 469 lines
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── capabilities/
├── package.json
├── dependencies/            # Blender bundled
└── scripts/
    └── build-backend-sidecar.ps1
```

---

## Contact

- Backend: Backend Team Lead
- Frontend: Frontend Team Lead  
- Mobile: Mobile Team Lead
- Desktop: Desktop Team Lead
- DevOps: Infrastructure Team
