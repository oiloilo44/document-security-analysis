# Enterprise DRM Analysis PoC

기업용 문서 보안 솔루션의 클라이언트 동작 방식과 보호 구조의 한계를 정리한 보안 연구 기록입니다.

이 저장소는 공개용으로 정리된 요약본입니다. 실제 제품 파일, 인증서, DLL, 네트워크 엔드포인트, 동작 가능한 우회 페이로드는 포함하지 않습니다.

## 내용

- 서버 API 모방 접근의 한계 분석
- 로컬 클라이언트 모듈 분석 과정 정리
- 신뢰된 뷰어 프로세스 모델의 구조적 위험 설명
- Python + Frida 기반 PoC 프레임워크 형태 예시
- 안전한 공개를 위해 핵심 후킹 로직은 제거

## 파일

```text
drm_hollowing_poc.py  레드랙션된 PoC 프레임워크 예시
README.md            연구 요약
```

## 범위

이 프로젝트는 보안 연구와 방어 관점의 설계 검토를 목적으로 작성했습니다. 상용 소프트웨어의 보호 조치를 우회하는 실제 코드나 운영 자료는 제공하지 않습니다.

## 기술 키워드

- Windows process instrumentation
- trusted process model
- filesystem minifilter behavior
- Python concurrency
- Frida IPC 구조
