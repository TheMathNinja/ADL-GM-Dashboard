# app.R explicitly sources its modules. Build-only helpers in R/ must not run
# when Shiny starts (the retired commissioner helper has external dependencies).
