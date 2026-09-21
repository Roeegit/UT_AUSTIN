# clean-ta-data.ps1
# Wipe all GCS test data for the TA accounts so they can run a clean exam.
#
# Covers:
#   results/{assignment}/{user}.json   — graded result blobs
#   {assignment}/{user}/               — uploaded submission files
#
# Does NOT touch:
#   complaints/   distress_events/     — session-keyed, rarely matter for TA tests
#   Cloud SQL exam_sessions rows       — use the admin UI "Invalidate Session" button
#                                        or call POST /api/admin/invalidate-session
#
# Usage:
#   .\clean-ta-data.ps1
#   .\clean-ta-data.ps1 -Bucket my-other-bucket

param(
    [string]$Bucket = "ai-exam-submission"
)

$TA_USERS = @("EinatNoyman", "shacharsl97")

Write-Host ""
Write-Host "=== TA data cleanup — bucket: $Bucket ===" -ForegroundColor Cyan
Write-Host ""

foreach ($user in $TA_USERS) {
    Write-Host "[$user]" -ForegroundColor Yellow

    # 1. Graded result blobs  (results/{any-assignment}/{user}.json)
    Write-Host "  Deleting result blobs..."
    gsutil -m rm -f "gs://$Bucket/results/**/$user.json" 2>$null

    # 2. Submission file directories  ({any-assignment}/{user}/*)
    Write-Host "  Deleting submission files..."
    gsutil -m rm -rf "gs://$Bucket/**/$user/" 2>$null

    Write-Host "  Done." -ForegroundColor Green
}

Write-Host ""
Write-Host "GCS cleanup complete." -ForegroundColor Cyan
Write-Host ""
Write-Host "REMINDER: Cloud SQL sessions are NOT cleared by this script." -ForegroundColor DarkYellow
Write-Host "To also reset the exam lock (allow retake), go to the admin viewer" -ForegroundColor DarkYellow
Write-Host "and click 'Invalidate Session' for each TA account, OR run:" -ForegroundColor DarkYellow
Write-Host ""
Write-Host "  POST /api/admin/invalidate-session" -ForegroundColor Gray
Write-Host "  Body: { `"github_username`": `"EinatNoyman`", `"assignment_name`": `"<name>`" }" -ForegroundColor Gray
Write-Host "        { `"github_username`": `"shacharsl97`", `"assignment_name`": `"<name>`" }" -ForegroundColor Gray
Write-Host ""
