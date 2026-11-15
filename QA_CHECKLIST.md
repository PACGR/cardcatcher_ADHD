# CARD CATCHER 현장 디버깅 체크리스트

자동검사로 확인할 수 없는 실제 모니터·키보드 동작을 파일럿 PC에서 한 번
확인하기 위한 목록이다. 테스트 참가자 번호는 `000`을 사용할 수 있다.

## 연습 프로그램 (`practice.py`)

- [ ] 참가자 정보창에서 취소하면 파일을 만들지 않고 종료된다.
- [ ] 빈 참가자 번호, `../001`, 문자 Seed를 입력하면 입력 오류창이 뜬다.
- [ ] `000`은 counterbalance cell 1로 기록된다.
- [ ] 시작 화면에서 SPACE를 길게 누르면, 키를 놓기 전에는 시작하지 않는다.
- [ ] Target에서 SPACE를 누르면 `correct_go`로 기록된다.
- [ ] Target에서 누르지 않으면 `go_omission`으로 기록된다.
- [ ] Near/Far에서 누르면 `commission`으로 기록된다.
- [ ] Near/Far에서 누르지 않으면 `correct_rejection`으로 기록된다.
- [ ] 100ms 미만 반응은 `anticipatory_excluded`로 기록된다.
- [ ] SPACE를 길게 눌러 다음 자극까지 유지하면 다음 시행에
  `space_held_at_onset=1`, `valid_for_primary=0`이 기록된다.
- [ ] 키를 길게 눌러도 운영체제 자동 반복이 여러 반응으로 기록되지 않는다.
- [ ] A, 방향키 등 다른 키는 반응으로 기록되지 않는다.
- [ ] ESC로 중단하면 완료된 시행까지만 저장되고 config가 `aborted`가 된다.
- [ ] 연습 1·2가 서로 다른 Target 세트로 각각 15시행씩 실행된다.
- [ ] 총 30시행 완료 후 SPACE는 무시되고, ESC로만 연습 화면을 종료한다.

## 본 시행 (`main.py`)

- [ ] Block A 시작 전 기준 카드가 화면의 목표 위치에 표시된다.
- [ ] Block A 시작 화면은 SPACE 입력 전까지 유지된다.
- [ ] 각 자극은 약 450ms, 전체 시행은 약 900ms로 기록된다.
- [ ] Block A 후 휴식 화면은 시간 제한 없이 유지된다.
- [ ] 휴식 화면에서 SPACE를 누르면 Block B가 시작된다.
- [ ] Block B에는 Block A와 다른 기준 세트가 사용된다.
- [ ] 한 세션에 Heavy-go와 Low-go가 각각 한 번씩 포함된다.
- [ ] 시행 중 ESC를 누르면 완료된 시행까지만 저장된다.
- [ ] 정상 완료 시 trial 300행과 schedule 300행이 생성된다.

## 파일과 분석

- [ ] `True/False` 성격의 값은 `1/0`, 해당 없음은 빈칸으로 저장된다.
- [ ] `target_pattern_id`와 `stimulus_pattern_id`가 1–84 범위다.
- [ ] schedule과 trials의 `global_trial_index`가 일치한다.
- [ ] `analysis/run_pipeline.py`가 연습 파일을 제외하고 정상 완료된다.
- [ ] `session_qc.tsv`에서 정상 세션은 `session_complete=True`다.
- [ ] 길게 누른 시행이 있으면 `held_key_at_onset_count`에서 확인된다.

## 디스플레이

- [ ] 전체화면에서 배경이 늘어나거나 잘리지 않는다.
- [ ] 기준 카드·현재 카드·안내문이 서로 겹치지 않는다.
- [ ] 실제 refresh rate가 `refresh_hz`에 기록된다.
- [ ] `actual_stimulus_duration_ms`와 `actual_trial_duration_ms`가 계획값에서
  한 프레임 이상 벗어나지 않는다.
