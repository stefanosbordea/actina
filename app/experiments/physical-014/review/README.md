# Independent physical 014 review

PASS for implementation and evidence integrity. Every upgrade gate fails. The primary conditional robust interface produces the exact raw-point water plan on every horizon. This is a verified negative result for this interface, not a new physical improvement.

## Timing clarification

The original `forecast-water-link.md` proposal fixed the interface and four arms before the 013 outcomes were read. Root then communicated that the primary 013 arm equaled raw before the final 014 protocol and implementation were completed. No 014 outcomes existed then. The completed implementation must therefore not be described as wholly preregistered or blinded to 013 results. Its final code and inputs were frozen before 014 planning and scoring. The four arms and nearest-binary64 mapping remained those of the earlier proposal.

The original frozen protocol is preserved byte for byte. Its opening claim of timing must be read with this explicit clarification. Both studies remain exploratory and reuse previously inspected periods.

## Preflight correction

Independent static review caught a source-loader defect before any historical execution. The first implementation parsed satellite missingness as textual true/false, while the pinned source uses 0/1. The corrected loader strictly checks 0/1, both feature clocks and the satellite interval start. A fixture with a missing row and malformed metadata now exercises these cases. The complete finding is preserved in `preflight-findings.md`.

All 12 final analytical fixtures passed in an independent execution. The stable reviewed hashes are recorded in `preflight-receipt-001.json`. Mapping uses the closest binary64 value consistent with strict `>600` and retains unchanged forecasts bitwise. The grid 1e-5 kWh flag is explicitly a numerical reporting threshold, separate from the inherited euro action floor.

## Historical replay

`check.py` imports no production helper. It verifies source, result and planning hashes, the retained exact event calls, all 2,990 water plans, 1,196 candidate interfaces, all six archived physical controls, source clocks, complete original-hour and physical-day masks, rational water residuals, hourly schedule ledgers, grid accounting, every paired aggregate and risk gate, and continuous/event metrics against the original model and persistence.

The checker exited 0 with 499,433 checks in 2.03 external wall seconds. Maximum independent arithmetic discrepancy was 2.39e-12 in the respective reported units. Maximum exact water residual was 15/8796093022208 m³, approximately 1.71e-12 m³, retained beneath the frozen 1e-6 m³ numerical tolerance. No production schedule was clipped or repaired.

The supplemental `identity-check.py` confirms all 299 recorded raw reproductions have exact equality and zero reported difference. It independently compares all 56,160 archived control outcome values with their 012 counterparts and finds exact equality. This does not claim an additional LP run by the reviewer. The original solver execution is evidenced by retained statuses, objective records and source-pinned receipts.

Of the 1,196 candidate inputs, 1,194 are exact raw identities and copy raw plans bitwise. Only mapped recency robust and mapped recency pooled on validation 2026-05-02 change input hours 11 and 12. Their maximum hourly production difference from raw is 4.3076473191548193e-13 m³. This is numerical scale, not a meaningful operating gain. All test plans and both conditional arms in both periods are exact raw copies. Every full physical and raw-control gate is false.

The complete receipts and stdout are `receipt-001.json`, `execution-001.log`, `identity-receipt-001.json` and `identity-execution-001.log`. `result.json` retains the primary audit's stdout. The source lock is `f206f24740bd76b02c7803f28f0e657ee2494bfdb8b53433ba22cf391052f6f5`, and the planning freeze is `f93411c7caa033841c297c6b129e93f01ddcd5a4a78b9efb6575ef24fabdba26`.

## Limits

The reviewer replayed solver statuses and objective caps without re-solving LPs or claiming a new optimality certificate. Tiny binary64 signs remain signed and flagged. Illustrative PV conversion, constant desalination efficiency, unlimited grid backup, estimated references and unverified publication availability remain limitations. An event bit does not uniquely determine a continuous irradiance forecast. This result describes only the fixed tested interface and does not establish plant savings, field readiness or general superiority.
