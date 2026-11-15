# CARD CATCHER

3×3 격자 내 3개 활성 위치(총 84개 조합, $D_4$ 대칭군 및 구조적 유사도 기반)를 사용하는 Go/No-Go 인지조절 실험 과제(PsychoPy)와 무의존성 데이터 품질관리·분석 파이프라인입니다.

## 과제 설계 요약

- **자극 구조**: 3×3 격자의 9개 셀 중 3개가 활성화된 84개 패턴(`000000111`–`111000000`, 패턴 ID `1`–`84`)을 기준으로 `Target`, `Near`, `Far` 자극을 구성합니다.
- **고정 본 시행 세트 및 Counterbalancing**:
  - 본 시행 고정 후보 세트: `set05`, `set10`, `set12`
  - 참가자 번호에 따라 [counterbalance_schedule.tsv](assets/codebooks/counterbalance_schedule.tsv)의 6개 cell에 순환 배정되며, 각 세션은 서로 다른 두 세트로 `Heavy-go` 블록(150시행: Target 112, Near 19, Far 19)과 `Low-go` 블록(150시행: Target 19, Near 19, Far 112)을 1회씩 수행합니다.
- **타이밍**: 자극 제시 `0.45초`, 반응창/SOA `0.90초`, 조기반응 기준 `0.10초` 미만(`premature_seconds=0.1`).
- **연습과 본 시행 분리**: 연습(`practice.py`)은 본 시행과 겹치지 않는 2개의 별도 세트로 각 15시행(총 30시행)을 진행하며, `ESC`로 종료 후 실험자가 요약 TSV를 확인하고 `main.py`를 별도 실행합니다.
- **물리 키 입력 추적**: `PhysicalKeyTracker`([key_events.py](key_events.py))가 OS 자동 반복 keydown을 중복 반응으로 세지 않고, 자극 시작 시점 키 누름 유지(`space_held_at_onset`)와 keydown/keyup 이벤트를 분리 기록합니다.

## 디렉터리 구조

```text
cardcatcher_ADHD/
├── practice.py              # 카드게임 버전 독립 연습 프로그램 (30시행)
├── main.py                  # 카드게임 버전 본 시행 프로그램 (Block A / 휴식 / Block B, 300시행)
├── runtime.py               # PsychoPy 자극 렌더링, 물리 키 추적 연동, 비동기 TSV 저장
├── schedule.py              # 3-of-9 패턴 ID, 세트 카탈로그, counterbalance 및 run 제약 스케줄링
├── display_utils.py         # 16:10 / 16:9 해상도 레이아웃 및 주사율 측정 유틸리티
├── key_events.py            # 물리적 keydown/keyup 추적 및 key_events TSV 기록기
├── session_utils.py         # 참가자 ID·세션·Seed 입력 검증
├── minimal_black/           # 장식 요소를 제거한 검은 배경 최소 시각요소 버전
│   ├── practice.py
│   ├── main.py
│   ├── runtime.py
│   └── README.md
├── analysis/                # 표준 라이브러리 기반 무의존성 QC 및 분석 파이프라인
│   ├── run_pipeline.py
│   ├── pipeline_config.json
│   ├── test_design.py
│   ├── test_key_events.py
│   ├── test_pipeline.py
│   ├── test_runtime_design.py
│   ├── test_user_behaviors.py
│   └── README.md
├── assets/
│   ├── backgrounds/         # 2880x1800 배경 및 layout JSON
│   ├── card-combinations/   # 전체 84개 3-of-9 카드 이미지
│   ├── card-examples/       # 예시 카드 이미지
│   ├── codebooks/           # pattern_codebook, stimulus_manifest, data_dictionary, counterbalance_schedule 등
│   └── sets/                # set01~set16 자극 PNG 및 선택/유사도 메타데이터
├── tools/                   # 자극 이미지·배경·D4 세트 순위 생성 PowerShell 스크립트
├── OPERATOR_GUIDE.md        # 현장 실험 진행자 안내서
└── QA_CHECKLIST.md          # 파일럿 PC 현장 디버깅 체크리스트
```

## 요구 사항

- **과제 실행 (데이터 수집)**: Windows 10/11, PsychoPy Standalone (Python 3.10+), 16:10 또는 16:9 디스플레이
- **분석 파이프라인 및 테스트**: Python 3 표준 라이브러리만으로 동작 (설계·런타임 테스트 전체 실행 시 PsychoPy Python 사용)

## 빠른 실행 방법

### 1. 카드게임 버전 (기본)

```powershell
# 1단계: 연습 (서로 다른 2개 세트로 총 30시행 후 ESC 종료)
& "C:\Program Files\PsychoPy\python.exe" practice.py

# 2단계: 본 시행 (동일 SubType / SubIdx / SubSes 입력, 총 300시행)
& "C:\Program Files\PsychoPy\python.exe" main.py
```

### 2. Minimal Black 버전

```powershell
& "C:\Program Files\PsychoPy\python.exe" minimal_black\practice.py
& "C:\Program Files\PsychoPy\python.exe" minimal_black\main.py
```

### 3. 데이터 분석 파이프라인

원본 `data/` 파일을 수정하지 않고 `analysis/output/`에 분석용 테이블과 QC 리포트를 생성합니다 (`*_practice_trials.tsv` 자동 제외).

```powershell
& "C:\Program Files\PsychoPy\python.exe" analysis\run_pipeline.py
```

### 4. 자동화 테스트 실행

```powershell
& "C:\Program Files\PsychoPy\python.exe" -m unittest discover -s analysis -p "test_*.py" -v
```

## 데이터 보안 및 버전 관리 정책

- 참가자 원자료(`data/`)와 분석 파생 산출물(`analysis/output/`)은 연구윤리 및 개인정보 보호를 위해 `.gitignore`에 의해 Git 추적 및 원격 저장소 업로드에서 제외되며 로컬 디스크에만 보관됩니다.
- 로컬에만 보관되는 과거 스냅샷·임시 참조 폴더(`Legacy/`, `tmp/`) 역시 `.gitignore`로 제외되어 있습니다.

## 참고 문서

- 현장 운영 가이드: [OPERATOR_GUIDE.md](OPERATOR_GUIDE.md)
- 현장 QA 체크리스트: [QA_CHECKLIST.md](QA_CHECKLIST.md)
- 분석 파이프라인 설명: [analysis/README.md](analysis/README.md)
- Minimal Black 버전 설명: [minimal_black/README.md](minimal_black/README.md)
- 로그 변수 코드북: [assets/codebooks/data_dictionary.tsv](assets/codebooks/data_dictionary.tsv)
