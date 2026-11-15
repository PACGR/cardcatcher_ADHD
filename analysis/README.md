# CARD CATCHER analysis pipeline

이 폴더는 `data/*/raw` 원본을 수정하지 않고 분석용 파생 파일을 생성합니다.
새 세션의 본 시행은 기존 호환 파일명인 `*_trials.tsv`와
`*_schedule.tsv`를 사용합니다. 기준 학습용 `*_practice_trials.tsv`,
`*_practice_schedule.tsv`, `*_practice_summary.tsv`는 별도로 보존되며
본 분석 파이프라인에서는 제외됩니다.

`space_held_at_onset=1`은 자극이 나타날 때부터 SPACE가 눌려 있던
시행입니다. 이 시행은 `valid_for_primary=0`으로 처리되며, 세션 QC의
`held_key_at_onset_count`와 요약표의 `n_held_at_onset`에서 확인할 수
있습니다. 운영체제의 자동 반복 keydown은 별도 반응으로 세지 않습니다.

## 실행

PsychoPy Python 또는 일반 Python 3로 프로젝트 루트에서 실행합니다.

```powershell
& 'C:\Program Files\PsychoPy\python.exe' analysis\run_pipeline.py
```

경로를 직접 지정할 수도 있습니다.

```powershell
& 'C:\Program Files\PsychoPy\python.exe' analysis\run_pipeline.py `
  --data-dir data `
  --stimulus-manifest assets\sets\all_sets_manifest.csv `
  --config analysis\pipeline_config.json `
  --output-dir analysis\output
```

## 산출물

- `processed_trials.tsv`: raw 열을 보존하고 QC·이전 trial·자극 특징·분석 포함 플래그를 추가한 모델용 long table
- `participant_summary.tsv`: 참가자 세션 × Practice/Low-go/Heavy-go 요약
- `participant_contrasts.tsv`: Heavy-go minus Low-go 참가자 내 대비
- `session_qc.tsv`: 스케줄 일치, timing, keyup, manifest 결합 품질
- `stimulus_summary.tsv`: 자극 패턴별 반응률과 연속 유사도 특징
- `sequence_summary.tsv`: run 길이·위치별 반응 및 RT 요약
- `analysis_manifest.json`: 설정, 입력 SHA-256, 출력 행 수, protocol 경고

## 주요 플래그

- `primary_include`: Practice가 아니고 `valid_for_primary=True`
- `rt_eligible`: main block의 유효하고 올바른 Target 반응이며 RT가 `[premature, response_window)` 범위
- `timing_warning`: 실제 자극 또는 trial 시간이 설정값에서 기본 5ms 초과
- `timing_bad_gt_frame`: 설정값에서 주사율 기준 한 프레임 초과
- `rt_outlier_mad`: 참가자 세션 × block type 안에서 `3 × 1.4826 × MAD` 초과
- `rt_include_strict`: RT eligible이면서 설정에 따라 timing bad와 MAD 이상치를 제외
- `keyup_quality_flag`: keyup/press duration 누락, 음수 또는 response window 초과

정확도·commission·omission은 `primary_include`를 사용하고, Target RT 요약은 `rt_include_strict`를 사용합니다. `keyup_quality_flag=True`인 세션에서는 `keyup_ms`와 `press_duration_ms`를 분석하지 않습니다.

## 분석 시 주의

1. `Block A/B`가 아니라 `block_type`의 `Low-go/Heavy-go`로 비교합니다.
2. Practice는 primary analysis에서 제외합니다.
3. `protocol_id`가 다른 세션을 그대로 합치지 않습니다.
4. raw data는 수정하지 않고 파생 열의 제외 사유를 함께 보존합니다.
5. Near/Far 외에 `stimulus_similarity_score`, Hamming, D4, 구조거리를 연속 예측변수로 사용할 수 있습니다.
