# Card Catcher 실행 안내

## 실행 전

1. PsychoPy에서 먼저 `practice.py`를 연다.
2. 참가자 정보를 입력한다.
   - `SubType`: 집단 코드
   - `SubIdx`: 참가자 번호
   - `SubSes`: 세션 번호
   - `Seed`: 보통 비워 둔다. 재현이 필요할 때만 기존 seed를 입력한다.
3. 참가자에게 왼쪽 기준 카드와 완전히 같은 카드에만 `SPACE`를 누르고,
   다른 카드에는 누르지 않는다고 설명한다.
4. 연습 종료 후 실험자가 `*_practice_trials.tsv`와
   `*_practice_summary.tsv`를 확인한다.
5. 본 시행을 진행할 때는 `main.py`를 별도로 실행하고, 연습과 동일한
   `SubType`, `SubIdx`, `SubSes`를 입력한다.

## 분리된 진행 순서

```text
practice.py
  → 연습 1: 15시행
  → 서로 다른 Target 세트로 연습 2: 15시행
  → "연습이 끝났습니다"
  → 실험자가 ESC로 종료
  → 실험자가 practice TSV 확인

main.py
  → "스페이스바를 눌러 블록A를 시작하시오"
  → 본 시행 Block A
  → 자기조절식 휴식 화면
  → SPACE 입력
  → 본 시행 Block B
  → 종료
```

- 연습은 서로 다른 Target 세트로 2회 연속 실행한다.
- 각 연습은 Target 5, Near 5, Far 5의 15시행이며, 총 30시행이다.
- 연습과 본 시행은 모두 자극 0.45초, 전체 반응창/SOA 0.9초를 사용한다.
- 연습에도 시행별 정답·오답 피드백이나 추가 대기시간이 없다.
- 통과하려면 Target 4/5 이상, Near+Far 8/10 이상, 전체 12/15 이상을
  모두 만족해야 한다. 이 판정은 실험자용 요약 TSV에만 기록된다.
- 참가자에게는 점수나 통과 여부를 표시하지 않는다.
- 연습 종료 화면은 `ESC`가 입력될 때까지 유지된다. `SPACE`로는
  종료하거나 본 시행으로 넘어가지 않는다.
- `main.py`는 연습을 포함하지 않으며, 실험자가 별도로 실행한다.
- 본 시행에는 정답·오답 피드백이 없다.
- Block A 시작 화면은 `SPACE` 입력 전까지 유지된다.
- Block A가 끝나면 별도의 고정 휴식시간을 사용하지 않고, Block B 시작
  화면에서 참가자가 원하는 만큼 쉰다.
- `ESC`를 누르면 중단되며, 중단 전까지 기록된 자료는 유지된다.
- `SPACE`를 길게 눌러 다음 자극이 시작될 때까지 유지하면 해당 시행은
  정답으로 계산하지 않고 `space_held_at_onset=1`로 기록한다.
- 키를 계속 누를 때 운영체제가 생성하는 자동 반복 keydown은 별도의
  반응으로 중복 계산하지 않는다.

## 참가자 화면 문구

### 연습 종료

```text
연습이 끝났습니다
```

- `SPACE`는 무시된다.
- 실험자가 `ESC`를 눌러야 연습 프로그램이 종료된다.
- 점수와 통과 여부는 참가자에게 표시하지 않는다.

### Block A 시작

```text
스페이스바를 눌러 블록A를 시작하시오
```

- 다른 규칙 설명이나 하단 `SPACE` 문구는 표시하지 않는다.

### Block A 종료 후 휴식 및 Block B 시작

```text
휴식 시간입니다.
준비가 되면 스페이스바를 눌러 블록 B를 시작하세요.
```

- 고정된 휴식시간은 없다.
- 참가자가 `SPACE`를 누르면 즉시 Block B가 시작된다.

## 세트와 counterbalancing

- 본 시행 후보는 `set05`, `set10`, `set12`로 고정되어 있다.
- 참가자 한 명은 이 중 서로 다른 두 세트를 사용한다.
- 참가자 번호에 따라 6개 counterbalance cell을 순환 배정한다.
- 각 cell에는 Heavy-go 한 블록과 Low-go 한 블록이 한 번씩 포함된다.
- 실제 배정표는 `assets/codebooks/counterbalance_schedule.tsv`에서 확인한다.

## 생성되는 파일

각 참가자의 `data/<집단-번호>/raw/` 폴더에 저장된다.

- `*_p01-p02_practice_schedule.tsv`: 두 연습의 30시행 계획
- `*_p01-p02_practice_trials.tsv`: 두 연습의 trial-level 원자료
- `*_p01-p02_practice_summary.tsv`: 연습 1·2별 정확도와 통과 여부
- `*_p01-p02_practice_config.json`: 연습 seed, 두 세트, 타이밍, 완료 상태
- `*_schedule.tsv`: 본 시행 300시행 계획
- `*_trials.tsv`: 본 시행 원자료
- `*_config.json`: 본 시행 seed, 세트 배정, 타이밍, 시작·종료 시각

## 코드북

- `assets/codebooks/pattern_codebook.tsv`: 3-of-9 패턴의 고정 ID 1–84
- `assets/codebooks/stimulus_manifest.tsv`: 모든 이미지와 패턴 ID의 연결
- `assets/codebooks/data_dictionary.tsv`: 로그 열의 정의와 결측 규칙
- `assets/codebooks/counterbalance_schedule.tsv`: 6개 배정 cell
- `assets/codebooks/main_set_triplet.tsv`: 고정 세트 선정 근거

## 분석

본 시행 분석은 기존처럼 다음 한 명령으로 실행한다.

```powershell
& "C:\Program Files\PsychoPy\python.exe" analysis\run_pipeline.py
```

분석 파이프라인은 `*_practice_trials.tsv`를 자동으로 제외한다. Heavy-go와
Low-go를 별도 프로그램으로 나누지 않고 `block_type`으로 구분한다.

## 보존본

변경 전 Python/PsychoPy 구조는
`Legacy/python-baseline-20260728/`에 보존되어 있다. 실제 수집 데이터와
PNG 자극은 중복 복사하지 않았다.
