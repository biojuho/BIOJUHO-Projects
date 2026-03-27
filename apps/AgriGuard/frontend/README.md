# AgriGuard Frontend

AgriGuard 프로젝트의 프론트엔드 애플리케이션입니다. React와 Vite를 기반으로 구축되었습니다.  
This is the frontend application for the AgriGuard project, built with React and Vite.

## 🛠 기술 스택 (Tech Stack)

- **프레임워크 (Framework):** React 19
- **빌드 도구 (Build Tool):** Vite
- **스타일링 (Styling):** Tailwind CSS

---

## 🚀 빠른 시작 (Quick Start)

이 프로젝트는 개발과 빌드 속도를 높이기 위해 Vite를 기본 설정으로 제공합니다.  
This template provides a minimal setup to get React working in Vite with Hot Module Replacement (HMR) and ESLint rules to maintain code quality.

### 설치 및 실행 (Installation & Running)

```bash
# 의존성 패키지 설치 (Install dependencies)
npm install

# 개발 서버 실행 (Start the development server)
npm run dev
```

### 공식 플러그인 (Official Plugins)

현재 다음의 두 가지 공식 플러그인을 사용할 수 있습니다:  
Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react): Fast Refresh를 위해 **Babel**을 사용합니다. / Uses Babel for Fast Refresh.
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc): Fast Refresh를 위해 **SWC**를 사용합니다. / Uses SWC for Fast Refresh.

---

## ⚡ React Compiler

현재 템플릿에는 React Compiler가 기본으로 활성화되어 있지 않습니다. 개발 및 빌드 성능에 영향을 미칠 수 있기 때문입니다. 추가하려면 [이 문서](https://react.dev/learn/react-compiler/installation)를 참고하세요.  
The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## 🧩 ESLint 설정 확장 (Expanding the ESLint configuration)

프로덕션용 애플리케이션을 개발하는 경우, 타입 인지(type-aware) 린팅 규칙이 포함된 TypeScript 사용을 권장합니다. TypeScript와 `typescript-eslint`를 프로젝트에 통합하는 방법은 [TS 템플릿](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts)에서 확인할 수 있습니다.  
If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
