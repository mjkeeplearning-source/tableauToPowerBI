# Layer vii — Desktop-open gate (real-workbook subset)

Windows CI runner launches `PBIDesktop.exe /Open <pbip>` and parses the
trace directory for canonical events: ReportLoaded, ModelLoaded,
RepairPrompt, ModelError, VisualError, AuthenticationNeeded,
AuthUIDisplayed. Pass criteria split by datasource tier. See spec §9
layer vii + §6 Stage 8 step 5. Populated in Plan 5.
