cap_manager_ui <- function(id) {
  ns <- shiny::NS(id)
  shiny::tagList(
    shiny::tags$link(rel="stylesheet", href="cap-manager.css?v=12"),
    shiny::div(class="cap-page",shiny::div(class="cap-manager",
      shiny::div(class="cap-team-controls",
        shiny::selectInput(ns("team"),"ADL Franchise",choices=NULL),
        shiny::actionButton(ns("refresh"),"Refresh ADL Rosters",class="btn-primary"),
        shiny::uiOutput(ns("freshness"))),
      shiny::uiOutput(ns("team_banner")),
      shiny::tabsetPanel(id=ns("cap_tab"), selected="2026 Cap Manager",
        shiny::tabPanel("2026 Cap Manager",
          shiny::div(class="cap-tab-content",
      bslib::card(shiny::uiOutput(ns("current")), shiny::uiOutput(ns("cash_status"))),
      shiny::div(class="cap-history-comparison",
        bslib::card_header("Weekly Ledger"),
        shiny::div(class="cap-history-pane",
          shiny::div(class="cap-comparison-body",shiny::uiOutput(ns("weekly_ledger")))),
        shiny::div(class="cap-history-pane",
          shiny::div(class="cap-comparison-body",
            shiny::radioButtons(ns("history_view"),NULL,c("Expenditures"="expenditures","Cap Space"="space"),inline=TRUE),
            shiny::div(class="cap-history-lines",
              shiny::checkboxGroupInput(ns("history_lines"),"Show lines",
                choices=stats::setNames(
                  as.vector(outer(c("Franchise","Conference","ADL"),c("Weekly","Cumulative avg."),paste,sep=" - ")),
                  c("Franchise (Weekly Spend)","Conference (Weekly avg.)","ADL (Weekly avg.)",
                    "Franchise (Cumulative avg.)","Conference (Cumulative avg.)","ADL (Cumulative avg.)")),
                selected="Franchise - Weekly",inline=TRUE)),
            shiny::uiOutput(ns("history_plot"),class="cap-history-chart")))))),
        shiny::tabPanel("2027 Cap Manager",
          shiny::div(class="cap-tab-content",
      bslib::card(bslib::card_header("Next-season cap and roster outlook"),
        shiny::uiOutput(ns("next_season")),
        shiny::tags$details(shiny::tags$summary("Next-season roster snapshot"),
          shiny::div(style="overflow-x:auto",shiny::tableOutput(ns("next_roster")))),
        shiny::tags$details(shiny::tags$summary("Draft-pick salary reserves"),
          shiny::div(style="overflow-x:auto",shiny::tableOutput(ns("next_picks"))))))),
        shiny::tabPanel("Scenario Builder",
          shiny::div(class="cap-tab-content",
      bslib::card(bslib::card_header("Build a Scenario"),
        shiny::div(class="cap-forward-controls",
          shiny::numericInput(ns("forward"), "Forward spending ($m)", value=0, min=0, step=.01),
          shiny::helpText("Total cap spending per remaining week, including salary adjustments and empty-slot charges. Player moves below are added to this amount."),
          shiny::actionButton(ns("use_current"), "Use current spending")
        ),
        shiny::div(class="cap-scenario-controls",
          shiny::div(class="cap-move-editor",
            shiny::selectInput(ns("action"), "Move type",
              c("Extend", "Drop", "Trade Away", "Trade For", "Sign Player", "Cash Trade")),
            shiny::conditionalPanel("input.action === 'Extend' || input.action === 'Drop' || input.action === 'Trade Away'",
              shiny::selectizeInput(ns("player"), "Player on your roster", choices=NULL), ns=ns),
            shiny::conditionalPanel("input.action === 'Sign Player'", ns=ns,
              shiny::textInput(ns("sign_name"),"Player name",value="New player"),
              shiny::numericInput(ns("sign_years"),"Contract years (including this season)",value=1,min=1,max=6,step=1),
              shiny::numericInput(ns("sign_salary"),"Final contract salary ($m)",value=1.1,min=1.1,step=.01),
              shiny::helpText("Adds one paid player at the salary entered. Existing empty-slot charges are recalculated.")),
            shiny::conditionalPanel("input.action === 'Trade For'", ns=ns,
              shiny::selectizeInput(ns("incoming"),"Player to acquire",choices=NULL),
              shiny::helpText("Adds one paid player at their current salary. Add Trade Away or Cash Trade moves for the other pieces.")),
            shiny::conditionalPanel("input.action === 'Cash Trade'", ns=ns,
              shiny::selectInput(ns("cash_partner"),"Trade partner",choices=NULL),
              shiny::radioButtons(ns("cash_direction"),"Cash direction",c("Receive cap space"="receive","Send cap space"="send")),
              shiny::numericInput(ns("cash_amount"),"Cash amount ($m)",value=.01,min=.01,step=.01),
              shiny::checkboxInput(ns("cash_qualifies"),"Both sides include an SD-minimum contract or a Round 1/2 pick",FALSE),
              shiny::uiOutput(ns("cash_preview")),
              shiny::helpText("Current-year cap space, in $0.01m increments. Positive net cash means received; negative means sent.")),
            shiny::uiOutput(ns("move_controls")),
            shiny::uiOutput(ns("move_preview")),
            shiny::uiOutput(ns("add_control"))),
          shiny::div(class="cap-move-queue",
            shiny::tags$h4("Scenario moves"),
            shiny::uiOutput(ns("moves")),
            shiny::selectInput(ns("remove_move"), "Remove a move", choices=NULL),
            shiny::div(class="cap-move-buttons",
              shiny::actionButton(ns("remove"), "Remove selected move"),
              shiny::actionButton(ns("reset"), "Reset all moves"))))),
      bslib::card(bslib::card_header("Scenario projection"), shiny::uiOutput(ns("projection"))))))
    ))
  )
}

cap_manager_server <- function(id, players_data, snapshots_data, history_data, season, active) {
  shiny::moduleServer(id, function(input, output, session) {
    ns <- session$ns
    data <- shiny::reactiveVal(cap_load_cache(season=season))
    error <- shiny::reactiveVal(NULL)
    moves <- shiny::reactiveVal(list())
    loaded <- FALSE
    refresh <- function(queue_shared=FALSE) {
      if(queue_shared) {
        shared <- trigger_shared_roster_refresh(reason="salary_cap_manager_button")
        shiny::showNotification(if(isTRUE(shared$ok))
          "Shared dashboard refresh queued. Refreshing this session from MFL now."
          else paste("Refreshing this session; shared refresh:",shared$reason),
          type=if(isTRUE(shared$ok)) "message" else "warning",duration=10)
      }
      result <- tryCatch(cap_fetch_data(season, players_data()), error=identity)
      if (inherits(result,"error")) {
        error(paste("Live refresh unavailable; showing the saved snapshot.", conditionMessage(result)))
        cash <- tryCatch(cap_refresh_cash(data(),season),error=identity)
        if(!inherits(cash,"error")) data(cash)
      } else {
        data(result); error(NULL); moves(list())
      }
    }
    shiny::observeEvent(active(), {
      if (isTRUE(active()) && !loaded) { loaded <<- TRUE; refresh() }
    })
    shiny::observeEvent(input$refresh, refresh(queue_shared=TRUE))
    shiny::observeEvent(players_data(), { if(loaded) refresh() },ignoreInit=TRUE)
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
    output$history_plot <- shiny::renderUI({
      shiny::req(input$team,input$history_view)
      chart <- cap_history_plot(cap_history_series(data(),input$team,input$history_view),
        input$history_lines,team()$franchise_cap,data()$league_cap,input$history_view)
      svg <- svglite::svgstring(width=7,height=4.6,standalone=FALSE)
      tryCatch(print(chart),finally=grDevices::dev.off())
      markup <- svg()
      # Browser text inherits the dashboard's Inter webfont, rather than rasterizing a server font.
      markup <- gsub(" textLength='[^']*' lengthAdjust='[^']*'", "", markup)
      shiny::div(role="img", `aria-label`="Weekly and cumulative average franchise, conference and ADL cap history. Use the controls to choose lines and expenditures or cap space.",
        shiny::HTML(markup))
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
    output$team_banner <- shiny::renderUI({
      shiny::req(input$team)
      brand <- cap_team_brand(players_data(),input$team)
      shiny::div(class="cap-team-banner",style=paste0("--cap-team-primary:",brand$primary,
        ";--cap-team-secondary:",brand$secondary,";--cap-team-text:",brand$text,";"),
        if(!is.na(brand$logo) && nzchar(brand$logo)) shiny::div(class="cap-team-logo",
          shiny::tags$img(src=brand$logo,alt=paste(brand$name,"logo"))),
        shiny::div(shiny::tags$h2(brand$name)))
    })
    output$freshness <- shiny::renderUI({
      if(is.null(data())) return(shiny::div(role="alert","Cap data is unavailable. Use Refresh to retry."))
      tagList(shiny::tags$p(class="cap-source",role="status",shiny::tags$strong(paste("Last Updated:",cap_time_et(data()$refreshed_at,"%b %d, %Y at %I:%M %p")))),
        if(!is.null(error())) shiny::div(class="alert alert-warning",role="alert",error()))
    })
    trade_candidates <- shiny::reactive({
      shiny::req(input$team)
      all <- data()$roster
      used <- vapply(moves(),function(m)m$player_id, "")
      all <- all[all$conference==roster()$conference[1] & all$franchise!=input$team & !all$player_id %in% used,]
      all[order(all$player),]
    })
    cash_changes <- function(move_list=moves()) vapply(move_list,function(m)m$cash_net %||% 0,numeric(1))
    cash_status <- shiny::reactive({
      status <- cap_cash_status(team()$net_cash_received,cash_changes(),data()$league_cap)
      partners <- unique(vapply(moves(),function(m)m$partner %||% "",""))
      for(partner in partners[nzchar(partners)]) {
        other <- data()$teams$net_cash_received[data()$teams$franchise==partner]
        changes <- vapply(moves(),function(m)if(identical(m$partner,partner)) -(m$cash_net %||% 0) else 0,numeric(1))
        status$valid <- status$valid && cap_cash_status(other,changes,data()$league_cap)$valid
      }
      status
    })
    shiny::observeEvent(list(input$team,data(),moves()), {
      candidates <- trade_candidates()
      shiny::updateSelectizeInput(session,"incoming",choices=stats::setNames(candidates$player_id,
        paste0(candidates$player," (",candidates$franchise,")")),
        selected=if(length(input$incoming)==1 && input$incoming %in% candidates$player_id) input$incoming else head(candidates$player_id,1),server=FALSE)
      partners <- sort(unique(data()$roster$franchise[data()$roster$conference==roster()$conference[1] &
        data()$roster$franchise!=input$team]))
      shiny::updateSelectInput(session,"cash_partner",choices=partners,
        selected=if(length(input$cash_partner)==1 && input$cash_partner %in% partners) input$cash_partner else head(partners,1))
    })
    output$move_controls <- shiny::renderUI({
      if(is.null(input$action)) return(NULL)
      if(input$action %in% c("Sign Player","Trade For","Cash Trade")) return(NULL)
      row <- selected()
      if(identical(input$action,"Trade Away")) return(shiny::helpText("Removes the player and salary without a drop penalty. Empty paid slots are recalculated."))
      if(identical(input$action,"Extend")) {
        p <- context()
        years <- if(is.null(p)) integer() else cap_extension_years(p, extension_week_current)
        if(!length(years)) return(shiny::div(role="status", if(is.null(p))
          "EXT data is not published for this player yet." else if(extension_week_current>16)
          "The in-season extension window is closed." else p$eligibility_note))
        tagList(shiny::selectInput(ns("years"),"Years to add",choices=years,selected=years[1]),
          shiny::helpText(paste("EXT pricing week:",extension_week_default,"\u2022",p$eligibility_note)),
          if(has_available_fifth_year_option(p) && !has_exercised_fifth_year_option(p))
            shiny::checkboxInput(ns("five_year"),"Include available fifth-year option",FALSE))
      } else {
        guarantee <- cap_guarantee(row, season)
        tagList(shiny::div(class="cap-guarantee",shiny::tags$strong("Contract guarantee at signing: "),
          if(is.na(guarantee)) "Unavailable - a drop estimate requires verified contract data." else
            switch(guarantee,FG="Fully guaranteed (FG)",SD="Standard (SD)",NG="Non-guaranteed (NG)")),
          shiny::checkboxInput(ns("claimed"),"Player is claimed on waivers (no penalty)",FALSE),
          shiny::checkboxInput(ns("accelerate"),"Accelerate next-year penalty into this year",FALSE),
          if(format(Sys.Date(),"%m-%d")<"07-01") shiny::checkboxInput(ns("july_tender"),"Use an available July 1 Tender",FALSE))
      }
    })
    preview <- shiny::reactive({
      if(identical(input$action,"Sign Player")) {
        salary <- input$sign_salary
        name <- trimws(input$sign_name %||% "")
        if(!nzchar(name) || length(salary)!=1 || !is.finite(salary) || salary<cap_vet_min(season) || abs(salary-round_salary(salary))>1e-8) return(NULL)
        years <- input$sign_years %||% 1
        if(length(years)!=1 || !is.finite(years) || years<1 || years>6 || years!=floor(years)) return(NULL)
        return(list(player_id=paste0("sign:",length(moves())+1),player=name,action="Sign Player",
          delta=salary,paid_delta=1,next_year=0,penalty=0,cash_net=0,contract_salary=salary,contract_years=years,
          detail=paste("Sign at",money(salary),"for",years,"years - adds one paid player")))
      }
      if(identical(input$action,"Trade For")) {
        p <- trade_candidates()
        p <- p[p$player_id==input$incoming,,drop=FALSE]
        if(nrow(p)!=1) return(NULL)
        return(list(player_id=p$player_id,player=p$player,action="Trade For",delta=p$prev_salary,
          paid_delta=1,next_year=0,penalty=0,cash_net=0,
          detail=paste("Acquire from",p$franchise,"at",money(p$prev_salary),"- adds one paid player")))
      }
      if(identical(input$action,"Cash Trade")) {
        amount <- input$cash_amount
        if(length(amount)!=1 || !is.finite(amount) || amount<=0 || abs(amount-round_salary(amount))>1e-8 || !isTRUE(input$cash_qualifies)) return(NULL)
        partner <- data()$teams[data()$teams$franchise==input$cash_partner,,drop=FALSE]
        if(nrow(partner)!=1 || partner$franchise==input$team ||
           !partner$franchise %in% data()$roster$franchise[data()$roster$conference==roster()$conference[1]]) return(NULL)
        net <- if(identical(input$cash_direction,"receive")) amount else -amount
        own <- cap_cash_status(team()$net_cash_received,c(cash_changes(),net),data()$league_cap)
        previous <- sum(vapply(moves(),function(m)if(identical(m$partner,input$cash_partner)) -(m$cash_net %||% 0) else 0,numeric(1)))
        other <- cap_cash_status(partner$net_cash_received,c(previous,-net),data()$league_cap)
        if(!own$valid || !other$valid) return(NULL)
        return(list(player_id=paste0("cash:",length(moves())+1),player=paste(input$cash_partner,"cash"),
          action="Cash Trade",delta=-net,paid_delta=0,next_year=0,penalty=0,cash_net=net,partner=input$cash_partner,
          detail=paste(if(net>0) "Receive" else "Send",money(amount),if(net>0) "from" else "to",input$cash_partner)))
      }
      row <- selected()
      used <- vapply(moves(),function(m) m$player_id,"")
      if(row$player_id %in% used) return(NULL)
      if(identical(input$action,"Trade Away")) {
        paid <- as.integer(cap_paid(row))
        return(list(player_id=row$player_id,player=row$player,action="Trade Away",
          delta=if(paid) -row$prev_salary else 0,paid_delta=-paid,next_year=0,penalty=0,cash_net=0,
          detail=paste("Trade away at",money(row$prev_salary),"- no drop penalty")))
      }
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
          contract_salary=result$new_salary,contract_years=result$final_years,
          detail=paste("Salary",money(row$prev_salary),"\u2192",money(result$new_salary),
            "\u2022",result$final_years,"total years"))
      } else {
        guarantee <- cap_guarantee(row,season)
        if(is.na(guarantee)) return(NULL)
        p <- context()
        fifth <- if(!is.null(p) && grepl("\\+$",row$contract)) fifth_year_display_salary(p) else NA_real_
        penalty <- cap_drop_penalty(row$prev_salary,row$prev_years,guarantee,row$injury,
          claimed=isTRUE(input$claimed),accelerate=isTRUE(input$accelerate),
          july_tender=isTRUE(input$july_tender),fifth_year=fifth)
        paid <- as.integer(cap_paid(row))
        removed <- if(paid) row$prev_salary else 0
        list(player_id=row$player_id,player=row$player,action="Drop",delta=round_salary(penalty$current-removed),
          penalty=penalty$current,next_year=penalty$next_year,paid_delta=-paid,vacancy=0,
          detail=paste("Current penalty",money(penalty$current),paste0("\u2022 ",season+1," penalty"),money(penalty$next_year),
            "\u2022 paid salary removed",money(removed),"\u2022",if(paid) "one fewer paid player" else "suspended taxi slot already excluded"))
      }
    })
    vacancy_delta <- function(move_list) {
      count_delta <- sum(vapply(move_list,function(m)m$paid_delta,numeric(1)))
      round_salary(max(0,45-current()$paid-count_delta)*cap_vet_min(season)-current()$vacancy)
    }
    output$cash_status <- shiny::renderUI({
      c <- cash_status()
      if(!c$valid) shiny::div(class="alert alert-warning","The cash balance is unavailable or a queued cash trade exceeds the net limit. Review the cash moves.")
    })

    output$cash_preview <- shiny::renderUI({
      amount <- input$cash_amount
      if(length(amount)!=1 || !is.finite(amount)) return(NULL)
      net <- if(identical(input$cash_direction,"receive")) amount else -amount
      c <- cap_cash_status(team()$net_cash_received,c(cash_changes(),net),data()$league_cap)
      partner <- data()$teams[data()$teams$franchise==input$cash_partner,,drop=FALSE]
      tagList(shiny::tags$p(paste("Your net after this trade:",money(c$net),"/ +/-",money(c$limit))),
        if(!c$valid) shiny::div(class="alert alert-warning","This trade exceeds your net cash limit or the cash ledger is unavailable."),
        if(nrow(partner)==1) {
          prior <- sum(vapply(moves(),function(m)if(identical(m$partner,input$cash_partner)) -(m$cash_net %||% 0) else 0,numeric(1)))
          other <- cap_cash_status(partner$net_cash_received,c(prior,-net),data()$league_cap)
          tagList(shiny::tags$p(paste(input$cash_partner,"net after this trade:",money(other$net))),
            if(!other$valid) shiny::div(class="alert alert-warning","This trade exceeds the partner's net cash limit or their ledger is unavailable."))
        })
    })
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
      labels <- vapply(moves(),function(m)paste(m$player,"\u2014",m$action),"")
      shiny::updateSelectInput(session,"remove_move",choices=stats::setNames(seq_along(labels),labels))
    })
    shiny::observeEvent(input$remove, {
      i <- suppressWarnings(as.integer(input$remove_move))
      if(length(i)==1 && !is.na(i) && i>=1 && i<=length(moves())) moves(moves()[-i])
    })
    metric <- function(label,value,note=NULL,change=NULL,lower_better=FALSE) {
      shiny::div(class="cap-metric",shiny::tags$span(label),
        shiny::tags$strong(if(is.na(value)) "\u2014" else money(value)),
        if(!is.null(note)) shiny::tags$small(class="cap-metric-note",note),
        if(!is.null(change) && is.finite(change)) shiny::tags$small(
          class=paste("cap-change",if(change==0) "neutral" else if((change<0)==lower_better) "favorable" else "unfavorable"),
          paste0(if(change>0) "+" else if(change<0) "-" else "",money(abs(change))," vs current")))
    }
    output$current <- shiny::renderUI({
      shiny::req(data(),input$team)
      c <- current(); b <- baseline(); cash <- cash_status()
      shiny::tagList(
        shiny::div(class="cap-equation",
          metric(paste(season,"Franchise Cap"),team()$franchise_cap,note=paste(
          money(data()$league_cap),"ADL Salary Cap +",money(round_salary(team()$franchise_cap-data()$league_cap)),season-1,"Cap Rollover")),
          shiny::div(class="cap-equation-sign",`aria-label`="minus","\u2212"),
          metric("Cumulative Expenditures",b$average,note=if(b$weeks) paste0("weekly avg. Weeks 1-",b$weeks) else "No recorded weeks"),
          shiny::div(class="cap-equation-sign",`aria-label`="equals","=",
            if(is.finite(b$average) && team()$franchise_cap-b$average > data()$league_cap*.1)
              shiny::tags$small("after rollover cap")),
          metric(paste("Current",season+1,"Rollover (Cap Space)"),b$expected_rollover,
          note=paste("Maximum rollover:",money(data()$league_cap*.1),"(10% of ADL Salary Cap)"))),
      shiny::div(class="cap-metrics",
        metric("Current Expenditures",c$spending,note=sprintf(
          "Salaries: %s \u2022 Empty Roster Slots: $%.2f (%d paid players) \u2022 Adjustments: %s",
          money(c$roster),c$vacancy,c$paid,money(c$adjustment))),
        metric("Effective Cap Space",b$effective),
        metric("Net Cash Charge via Trades",-team()$net_cash_received,
          note=paste0("Min Allowed: -",money(cash$limit)," | Max Allowed: ",money(cash$limit)," (5% of ADL Salary Cap)")),
        shiny::div(class="cap-equation cap-equation-projected",
          metric(paste(season,"Franchise Cap"),team()$franchise_cap,note=paste(
            money(data()$league_cap),"ADL Salary Cap +",money(round_salary(team()$franchise_cap-data()$league_cap)),season-1,"Cap Rollover")),
          shiny::div(class="cap-equation-sign",`aria-label`="minus","\u2212"),
          metric("Projected Expenditures (at current spending)",b$projected_average),
          shiny::div(class="cap-equation-sign",`aria-label`="equals","=",
            if(is.finite(b$projected_average) && team()$franchise_cap-b$projected_average > data()$league_cap*.1)
              shiny::tags$small("after rollover cap")),
          metric(paste("Projected Rollover to",season+1,"(at current spending)"),b$projected_rollover,
            note=paste("Maximum rollover:",money(data()$league_cap*.1),"(10% of ADL Salary Cap)")))))
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
        metric("Scenario forward spending",s$forward),
        metric("Projected Expenditures (scenario)",s$projected_average,
          change=round_salary(s$projected_average-b$projected_average),lower_better=TRUE),
        metric(paste("Projected Rollover to",season+1,"(scenario)"),s$projected_rollover,
          note=paste("Maximum rollover:",money(data()$league_cap*.1),"(10% of ADL Salary Cap)"),
          change=round_salary(s$projected_rollover-b$projected_rollover))),
        shiny::tags$p(paste(s$weeks,"recorded weeks +",s$remaining,"weeks at",money(s$forward),
          "\u2022 maximum rollover",money(data()$league_cap*.1))),
        if(s$remaining==0) shiny::div(class="alert alert-info","All 17 weeks are recorded. Moves and forward spending cannot change this year's rollover."),
        if(s$projected_rollover<0) shiny::div(class="alert alert-warning",role="status","This scenario projects spending above the franchise cap."),
        shiny::tags$p(paste("Scenario moves add",money(s$delta),"to forward spending, including",money(vacancy_delta(moves())),
          "in empty-slot charges. Added next-year penalties:",money(sum(vapply(moves(),function(m)m$next_year,numeric(1)))))))
    })
    output$weekly_ledger <- shiny::renderUI({
      shiny::req(data(),input$team)
      ledger <- data()$ledger
      if(is.null(ledger) || !nrow(ledger)) return(shiny::tags$p("Weekly Ledger is unavailable. Use Refresh ADL Rosters to retry."))
      ledger <- ledger[ledger$franchise==input$team,,drop=FALSE]
      ledger <- ledger[order(ledger$week),,drop=FALSE]
      if(!nrow(ledger)) return(shiny::tags$p("No completed weekly snapshots are recorded yet."))
      fields <- c("A","IR","S","TE","Yrs","Ill?","Paid","Vac$","RostSal","Adj","Corr","Final")
      definitions <- c("Active roster players","Injured-reserve players","Suspended players",
        "Non-suspended taxi players","Contract years excluding IR and suspended taxi",
        "Official illegal-roster flag","Paid players, excluding suspended taxi",
        "Veteran-minimum charges for paid slots below 45","Paid roster salaries",
        "Salary adjustments","Corrections","Vac$ + RostSal + Adj + Corr")
      currency <- c("Vac$","RostSal","Adj","Corr","Final")
      format_cell <- function(value,field,average=FALSE) {
        if(field=="Ill?") return(as.character(value))
        if(is.na(value)) return("\u2014")
        if(field %in% currency) return(sprintf(if(field=="Final") "$%.2fm" else "$%.2f",round_salary(as.numeric(value))))
        if(average) sprintf("%.0f",value) else format(value,trim=TRUE,scientific=FALSE)
      }
      cumulative <- cap_ledger_cumulative(ledger)
      flags <- sum(!is.na(ledger[["Ill?"]]) & nzchar(ledger[["Ill?"]]))
      shiny::tagList(shiny::div(class="cap-ledger-scroll",
        shiny::tags$table(class="table table-striped cap-ledger",
          shiny::tags$thead(shiny::tags$tr(shiny::tags$th("Week",scope="col"),
            lapply(seq_along(fields),function(i) shiny::tags$th(fields[i],title=definitions[i],scope="col")))),
          shiny::tags$tbody(lapply(seq_len(nrow(ledger)),function(i) shiny::tags$tr(
            shiny::tags$th(paste("Week",ledger$week[i]),scope="row"),
            lapply(fields,function(field) shiny::tags$td(format_cell(ledger[[field]][i],field)))))),
          shiny::tags$tfoot(shiny::tags$tr(shiny::tags$th(shiny::tags$strong("Average"),scope="row"),
            lapply(fields,function(field) shiny::tags$td(shiny::tags$strong(if(field=="Ill?")
              as.character(flags) else format_cell(cumulative[[field]],field,average=TRUE)))))))),
        shiny::tags$p(class="cap-source","Hover over a column heading for its definition."))
    })
    next_outlook <- shiny::reactive({
      shiny::req(input$team)
      tryCatch(cap_next_outlook(data(),input$team,moves(),scenario()$projected_rollover),error=identity)
    })
    output$next_season <- shiny::renderUI({
      n <- next_outlook()
      if(inherits(n,"error")) return(shiny::div(class="alert alert-warning",conditionMessage(n)))
      b <- cap_next_outlook(data(),input$team,list(),baseline()$projected_rollover)
      tagList(shiny::div(class="cap-metrics",
        metric(paste(n$year,"projected ADL league cap"),n$league_cap),
        metric(paste(n$year,"projected franchise cap"),n$franchise_cap,note=paste("Includes scenario rollover",money(n$rollover))),
        metric(paste(n$year,"projected expenditures"),n$spending,change=round_salary(n$spending-b$spending),lower_better=TRUE),
        metric(paste(n$year,"projected cap space"),n$space,change=round_salary(n$space-b$space)),
        metric("Returning players and assumed ERFA salaries",round_salary(n$salaries-sum(n$picks$salary))),
        metric("Projected rookie salaries",round_salary(sum(n$picks$salary))),
        metric("Recorded next-year salary adjustments",n$official_adjustments,note="Contract Admin; includes 2026 drops already recorded"),
        metric("Added next-year penalties from scenario drops",n$scenario_penalties),
        metric("Next-year empty-slot spending",n$vacancy,note=paste(n$empty,"empty paid slots at",money(cap_vet_min(n$year))))),
        shiny::tags$p(paste(n$paid,"projected paid players, including",n$erfas,"assumed ERFA tags and",nrow(n$picks),"draft picks.")),
        shiny::tags$p("Changes compare with next season at current spending and no queued moves. Empty spots are paid-slot reserves below 45, after including assumed rookies and ERFA tags."),
        shiny::tags$p("Projection assumes all owned draft picks are signed and all retained players return to paid status; current IR and suspension exclusions do not automatically carry forward. Expiring non-ERFAs leave unless extended in this scenario. ERFA tags assume the shared eligibility projection; RFA/franchise tags and unexercised fifth-year options are not assumed. No future cash trades or other unrecorded adjustments are assumed."),
        shiny::tags$p("CHI projection methods: linear ADL cap fit to 2022-2026; rookie-class wages grow by the 2026/2025 total first-year pool ratio (11.0007%); existing contracts rise 10%. Franchise cap = projected league cap + scenario rollover. All amounts are nominal next-season dollars."),
        shiny::tags$p(paste("Draft slots:",data()$next_season$draft_source,
          "ERFA accrued-season observations through Week",data()$next_season$tag_through_week,
          "with remaining-season accrual projected. Outlook inputs updated",cap_time_et(data()$next_season$refreshed_at))))
    })
    output$next_roster <- shiny::renderTable({
      n <- next_outlook(); shiny::validate(shiny::need(!inherits(n,"error"),"Next-season roster unavailable."))
      r <- n$roster; r <- r[order(r$next_years==0,r$player),]
      data.frame(Player=r$player,`Next-season status`=r$next_status,
        `Years remaining next season`=r$next_years,`Next-season salary`=vapply(r$next_salary,money,""),check.names=FALSE)
    },striped=TRUE,rownames=FALSE)
    output$next_picks <- shiny::renderTable({
      n <- next_outlook(); shiny::validate(shiny::need(!inherits(n,"error"),"Draft reserves unavailable."))
      p <- n$picks
      if(!nrow(p)) return(data.frame(Note="No owned picks in the next draft."))
      data.frame(Round=p$round,Original=p$original,`Projected slot`=p$slot,
        `Projected first-year salary`=vapply(p$salary,money,""),check.names=FALSE)
    },striped=TRUE,rownames=FALSE)
    output$moves <- shiny::renderUI({
      if(!length(moves())) return(shiny::tags$p("No moves added. Choose a move type, preview it, and add it to the queue. Stack signings, trades, cash, drops and extensions in one scenario."))
      tagList(shiny::tags$ol(class="cap-queue",lapply(seq_along(moves()),function(i) {
        m <- moves()[[i]]
        vacancy <- vacancy_delta(moves()[seq_len(i)])-if(i>1) vacancy_delta(moves()[seq_len(i-1)]) else 0
        shiny::tags$li(shiny::tags$strong(paste(m$action,"-",m$player)),shiny::tags$p(m$detail),
          shiny::tags$small(paste("Net spending change (with slots):",money(round_salary(m$delta+vacancy)))))
      })), shiny::div(class="cap-queue-total",shiny::tags$strong(paste("Whole scenario:",money(scenario()$delta),"net spending change")),
        shiny::tags$p(paste(current()$paid+sum(vapply(moves(),function(m)m$paid_delta,numeric(1))),"paid players after moves"))))
    })
  })
}

