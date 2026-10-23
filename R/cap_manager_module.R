cap_manager_ui <- function(id) {
  ns <- shiny::NS(id)
  bslib::layout_sidebar(
    sidebar=bslib::sidebar(width=310,
      shiny::selectInput(ns("team"), "ADL team", choices=NULL),
      shiny::actionButton(ns("refresh"), "Refresh live cap data", class="btn-primary"),
      shiny::uiOutput(ns("freshness")),
      shiny::hr(),
      shiny::numericInput(ns("forward"), "Forward spending ($m)", value=0, min=0, step=.01),
      shiny::helpText("Total cap spending per remaining week, including salary adjustments and empty-slot charges. Player moves below are added to this amount."),
      shiny::actionButton(ns("use_current"), "Use current spending"),
      shiny::hr(),
      shiny::selectizeInput(ns("player"), "Player on your roster", choices=NULL),
      shiny::radioButtons(ns("action"), "What-if move", c("Extend", "Drop"), inline=TRUE),
      shiny::uiOutput(ns("move_controls")),
      shiny::uiOutput(ns("move_preview")),
      shiny::uiOutput(ns("add_control")),
      shiny::actionButton(ns("reset"), "Reset all moves")),
    shiny::tags$link(rel="stylesheet", href="cap-manager.css?v=1"),
    shiny::div(class="cap-manager",
      bslib::card(bslib::card_header("Current salary cap"), shiny::uiOutput(ns("current"))),
      bslib::card(bslib::card_header("End-of-year projection"), shiny::uiOutput(ns("projection"))),
      bslib::card(bslib::card_header("Your what-if moves"), shiny::uiOutput(ns("moves")),
        shiny::selectInput(ns("remove_move"), "Remove a move", choices=NULL),
        shiny::actionButton(ns("remove"), "Remove selected move")),
      bslib::card(bslib::card_header("How the numbers work"),
        shiny::tags$p("All amounts are $m. Current spending = paid roster salaries + MFL salary adjustments + veteran minimum Ã— paid slots below 45. Suspended taxi players are excluded from paid salary and slot counts; IR salaries count."),
        shiny::tags$p("Current average and expected rollover use completed Contract Admin snapshots, including corrections. Effective Cap Space matches Cap Rollover: (franchise cap âˆ’ rounded current average) Ã— 17 Ã· remaining weeks; after Week 17 it is cap minus average."),
        shiny::tags$p("Projections hold recorded weeks fixed and apply forward spending plus simulated move changes to every remaining week. Rollover is capped at 10% of the ADL cap; negative rollover remains visible. Next-year penalties are shown separately and are not deducted from this year's rollover."),
        shiny::tags$p("Simulations only. Extensions use the EXT calculator's eligibility, pricing, six-year limit and published PR data. Drops assume the player clears waivers unless selected otherwise. An empty slot can still cost the veteran minimum; replacing that slot at the veteran minimum has the same cap cost."),
        shiny::tags$a(href="https://themathninja.github.io/ADL-Commissioner-Dashboard/salary-cap-accounting.html", "Official cap accounting", target="_blank")))
  )
}

cap_manager_server <- function(id, players_data, snapshots_data, history_data, season, active) {
  shiny::moduleServer(id, function(input, output, session) {
    ns <- session$ns
    data <- shiny::reactiveVal(cap_load_cache(season=season))
    error <- shiny::reactiveVal(NULL)
    moves <- shiny::reactiveVal(list())
    loaded <- FALSE
    refresh <- function() {
      result <- tryCatch(cap_fetch_data(season, players_data()), error=identity)
      if (inherits(result,"error")) {
        error(paste("Live refresh unavailable; showing the saved snapshot.", conditionMessage(result)))
      } else {
        data(result); error(NULL); moves(list())
      }
    }
    shiny::observeEvent(active(), {
      if (isTRUE(active()) && !loaded) { loaded <<- TRUE; refresh() }
    })
    shiny::observeEvent(input$refresh, refresh())
    shiny::observeEvent(data(), {
      choices <- data()$teams$franchise
      shiny::updateSelectInput(session,"team",choices=sort(choices),
        selected=if (length(input$team)==1 && input$team %in% choices) input$team else sort(choices)[1])
    })
    roster <- shiny::reactive({
      shiny::req(data(), input$team)
      data()$roster[data()$roster$franchise==input$team,,drop=FALSE]
    })
    team <- shiny::reactive({
      shiny::req(data(), input$team)
      data()$teams[data()$teams$franchise==input$team,,drop=FALSE]
    })
    current <- shiny::reactive(cap_spending(roster(), team()$adjustment, cap_vet_min(season)))
    baseline <- shiny::reactive({
      i <- match(input$team, data()$teams$franchise)
      cap_projection(data()$finals[i,], team()$franchise_cap, data()$league_cap, current()$spending)
    })
    shiny::observeEvent(list(input$team,data()), {
      shiny::req(input$team, current())
      moves(list())
      shiny::updateNumericInput(session,"forward",value=current()$spending)
    })
    shiny::observeEvent(input$use_current, shiny::updateNumericInput(session,"forward",value=current()$spending))
    # Selection changes must not rebuild their own picker. A team roster is
    # small enough to keep its searchable choices entirely in the browser.
    shiny::observeEvent(list(roster(), moves()), {
      available <- roster()
      used <- vapply(moves(), function(m) m$player_id, "")
      available <- available[!available$player_id %in% used,]
      available <- available[order(available$player),]
      shiny::updateSelectizeInput(session,"player",choices=stats::setNames(available$player_id,available$player),
        selected=if(length(input$player)==1 && input$player %in% available$player_id) input$player else head(available$player_id, 1), server=FALSE)
    })
    selected <- shiny::reactive({
      shiny::req(input$player)
      row <- roster()[roster()$player_id==input$player,,drop=FALSE]
      shiny::req(nrow(row)==1)
      row
    })
    context <- shiny::reactive({
      row <- selected()
      p <- players_data()
      p <- p[p$conference==row$conference & p$player_id==row$player_id,,drop=FALSE]
      if(nrow(p)!=1) return(NULL)
      for (field in c("prev_salary","prev_years","contract","franchise","roster_status")) p[[field]] <- row[[field]]
      # Current ownership/contract comes from live MFL, never an older weekly roster.
      ext_player_context(p, snapshots_data(), tibble::tibble(), history_data(),
        extension_week_default, season, historical=FALSE)
    })
    output$freshness <- shiny::renderUI({
      if(is.null(data())) return(shiny::div(role="alert","Cap data is unavailable. Use Refresh to retry."))
      tagList(shiny::tags$p(class="cap-source",paste("Data as of",data()$refreshed_at,"UTC.",
        baseline()$weeks,"of 17 snapshots recorded.","Vet minimum:",money(cap_vet_min(season)))),
        if(!is.null(error())) shiny::div(class="alert alert-warning",role="alert",error()))
    })
    output$move_controls <- shiny::renderUI({
      row <- selected()
      if(identical(input$action,"Extend")) {
        p <- context()
        years <- if(is.null(p)) integer() else cap_extension_years(p, extension_week_current)
        if(!length(years)) return(shiny::div(role="status", if(is.null(p))
          "EXT data is not published for this player yet." else if(extension_week_current>16)
          "The in-season extension window is closed." else p$eligibility_note))
        tagList(shiny::selectInput(ns("years"),"Years to add",choices=years,selected=years[1]),
          shiny::helpText(paste("EXT pricing week:",extension_week_default,"â€¢",p$eligibility_note)),
          if(has_available_fifth_year_option(p) && !has_exercised_fifth_year_option(p))
            shiny::checkboxInput(ns("five_year"),"Include available fifth-year option",FALSE))
      } else {
        guarantee <- cap_guarantee(row, season)
        tagList(shiny::selectInput(ns("guarantee"),"Contract guarantee at signing",
          choices=c("Non-guaranteed (NG)"="NG","Standard (SD)"="SD","Fully guaranteed (FG)"="FG"),
          selected=if(is.na(guarantee)) "SD" else guarantee),
          shiny::helpText(if(is.na(guarantee)) "Guarantee could not be identified. Confirm its level at signing before using this estimate." else
            paste("Detected:",guarantee,"from",row$contract,"â€” verify any special contract treatment.")),
          shiny::checkboxInput(ns("claimed"),"Player is claimed on waivers (no penalty)",FALSE),
          shiny::checkboxInput(ns("accelerate"),"Accelerate next-year penalty into this year",FALSE),
          if(format(Sys.Date(),"%m-%d")<"07-01") shiny::checkboxInput(ns("july_tender"),"Use an available July 1 Tender",FALSE))
      }
    })
    preview <- shiny::reactive({
      row <- selected()
      used <- vapply(moves(),function(m) m$player_id,"")
      if(row$player_id %in% used) return(NULL)
      if(identical(input$action,"Extend")) {
        p <- context()
        if(is.null(p)) return(NULL)
        years <- suppressWarnings(as.integer(input$years))
        if(length(years)!=1 || !years %in% cap_extension_years(p,extension_week_current)) return(NULL)
        fifth <- if(has_exercised_fifth_year_option(p) ||
          (has_available_fifth_year_option(p) && isTRUE(input$five_year))) fifth_year_display_salary(p) else NA_real_
        result <- extension_breakdown(p,years,extension_week_default,salary_curves,fifth_year_option=fifth)
        if(!is.finite(result$new_salary)) return(NULL)
        delta <- if(cap_paid(row)) round_salary(result$new_salary-row$prev_salary) else 0
        list(player_id=row$player_id,player=row$player,action=paste("Extend +",years,"years"),
          delta=delta,penalty=0,next_year=0,vacancy=0,paid_delta=0,
          detail=paste("Salary",money(row$prev_salary),"â†’",money(result$new_salary),
            "â€¢",result$final_years,"total years"))
      } else {
        shiny::req(input$guarantee)
        p <- context()
        fifth <- if(!is.null(p) && grepl("\\+$",row$contract)) fifth_year_display_salary(p) else NA_real_
        penalty <- cap_drop_penalty(row$prev_salary,row$prev_years,input$guarantee,row$injury,
          claimed=isTRUE(input$claimed),accelerate=isTRUE(input$accelerate),
          july_tender=isTRUE(input$july_tender),fifth_year=fifth)
        paid <- as.integer(cap_paid(row))
        removed <- if(paid) row$prev_salary else 0
        list(player_id=row$player_id,player=row$player,action="Drop",delta=round_salary(penalty$current-removed),
          penalty=penalty$current,next_year=penalty$next_year,paid_delta=-paid,vacancy=0,
          detail=paste("Current penalty",money(penalty$current),"â€¢ next year",money(penalty$next_year),
            "â€¢ paid salary removed",money(removed),"â€¢",if(paid) "one fewer paid player" else "suspended taxi slot already excluded"))
      }
    })
    vacancy_delta <- function(move_list) {
      count_delta <- sum(vapply(move_list,function(m)m$paid_delta,numeric(1)))
      round_salary(max(0,45-current()$paid-count_delta)*cap_vet_min(season)-current()$vacancy)
    }
    output$move_preview <- shiny::renderUI({
      p <- preview()
      if(is.null(p)) return(NULL)
      vacancy <- round_salary(vacancy_delta(c(moves(),list(p)))-vacancy_delta(moves()))
      shiny::div(class="cap-move-preview",shiny::tags$p(p$detail),
        shiny::tags$p(paste("Added empty-slot spending:",money(vacancy),"per remaining week.")),
        shiny::tags$strong(paste("Net spending change:",money(round_salary(p$delta+vacancy)))),
        if(p$action=="Drop") shiny::tags$p("If the drop leaves fewer than 45 paid players, an unfilled slot or a vet-min replacement costs the same."))
    })
    output$add_control <- shiny::renderUI({
      if(is.null(preview())) return(NULL)
      shiny::actionButton(ns("add"),"Add move to scenario",class="btn-primary")
    })
    shiny::observeEvent(input$add, {
      p <- preview(); shiny::req(p)
      moves(c(moves(),list(p)))
    })
    shiny::observeEvent(input$reset,moves(list()))
    shiny::observe({
      labels <- vapply(moves(),function(m)paste(m$player,"â€”",m$action),"")
      shiny::updateSelectInput(session,"remove_move",choices=stats::setNames(seq_along(labels),labels))
    })
    shiny::observeEvent(input$remove, {
      i <- suppressWarnings(as.integer(input$remove_move))
      if(length(i)==1 && !is.na(i) && i>=1 && i<=length(moves())) moves(moves()[-i])
    })
    metric <- function(label,value) shiny::div(class="cap-metric",shiny::tags$span(label),
      shiny::tags$strong(if(is.na(value)) "â€”" else money(value)))
    output$current <- shiny::renderUI({
      shiny::req(data(),input$team)
      c <- current(); b <- baseline()
      tagList(shiny::div(class="cap-metrics",
        metric("Current cap spending",c$spending),metric("Current avg cap spending",b$average),
        metric("Current franchise cap",team()$franchise_cap),metric("Current expected rollover",b$expected_rollover),
        metric("Spending for empty roster slots",c$vacancy),metric("Effective Cap Space",b$effective)),
        shiny::tags$p(paste(c$paid,"paid players â€¢",c$empty,"empty paid slots â€¢ roster salaries",money(c$roster),
          "â€¢ salary adjustments",money(c$adjustment))))
    })
    scenario <- shiny::reactive({
      shiny::validate(shiny::need(length(input$forward)==1 && is.finite(input$forward) && input$forward>=0,
        "Enter a non-negative forward spending amount."))
      delta <- sum(vapply(moves(),function(m)m$delta,numeric(1)))+vacancy_delta(moves())
      forward <- round_salary(input$forward+delta)
      shiny::validate(shiny::need(forward>=0,"The resulting forward spending cannot be negative."))
      i <- match(input$team,data()$teams$franchise)
      p <- cap_projection(data()$finals[i,],team()$franchise_cap,data()$league_cap,forward)
      c(p,list(forward=forward,delta=round_salary(delta)))
    })
    output$projection <- shiny::renderUI({
      shiny::req(data(),input$team)
      b <- baseline(); s <- scenario()
      tagList(shiny::div(class="cap-metrics",
        metric("At current spending: projected avg",b$projected_average),
        metric("At current spending: projected rollover",b$projected_rollover),
        metric("Scenario forward spending",s$forward),metric("Scenario projected avg",s$projected_average),
        metric("Scenario projected rollover",s$projected_rollover),
        metric("Rollover change vs current pace",round_salary(s$projected_rollover-b$projected_rollover))),
        shiny::tags$p(paste(s$weeks,"recorded weeks +",s$remaining,"weeks at",money(s$forward),
          "â€¢ maximum rollover",money(data()$league_cap*.1))),
        if(s$remaining==0) shiny::div(class="alert alert-info","All 17 weeks are recorded. Moves and forward spending cannot change this year's rollover."),
        if(s$projected_rollover<0) shiny::div(class="alert alert-warning",role="status","This scenario projects spending above the franchise cap."),
        shiny::tags$p(paste("Scenario moves add",money(s$delta),"to forward spending, including",money(vacancy_delta(moves())),
          "in empty-slot charges. Added next-year penalties:",money(sum(vapply(moves(),function(m)m$next_year,numeric(1)))))))
    })
    output$moves <- shiny::renderUI({
      if(!length(moves())) return(shiny::tags$p("No moves added. Pick a rostered player to preview an extension or drop."))
      shiny::tags$ul(lapply(moves(),function(m)shiny::tags$li(shiny::tags$strong(paste(m$player,"â€”",m$action)),
        shiny::tags$p(m$detail))))
    })
  })
}
