cap_manager_ui <- function(id) {
  ns <- shiny::NS(id)
  shiny::tagList(
    shiny::tags$link(rel="stylesheet", href="cap-manager.css?v=20"),
    shiny::div(class="cap-page",shiny::div(class="cap-manager",
      shiny::div(class="cap-team-controls",
        shiny::selectInput(ns("team"),"ADL Franchise",choices=NULL),
        shiny::actionButton(ns("refresh"),"Refresh ADL Rosters",class="btn-primary"),
        shiny::uiOutput(ns("freshness"))),
      shiny::uiOutput(ns("team_banner")),
      shiny::tabsetPanel(id=ns("cap_tab"), selected="2026 Cap Manager",
        shiny::tabPanel("2026 Cap Manager",
          shiny::div(class="cap-tab-content",
      bslib::card(shiny::uiOutput(ns("current"),class="cap-current-summary"), shiny::uiOutput(ns("cash_status"))),
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
        shiny::tags$h4("Next-season roster snapshot",class="cap-roster-heading"),
        shiny::uiOutput(ns("next_roster"))))),
        shiny::tabPanel("Scenario Builder",
          shiny::div(class="cap-tab-content",
      bslib::card(bslib::card_header("Build a Scenario"),
        shiny::div(class="cap-scenario-controls",
          shiny::div(class="cap-move-editor",
            shiny::selectInput(ns("action"), "Transaction",
              c("Extend", "Drop", "Trade Away", "Trade For", "Sign Player", "Cash Trade")),
            shiny::conditionalPanel("input.action === 'Extend' || input.action === 'Drop' || input.action === 'Trade Away'",
              shiny::selectizeInput(ns("player"), "Player", choices=NULL), ns=ns),
            shiny::conditionalPanel("input.action === 'Sign Player'", ns=ns,
              shiny::selectizeInput(ns("sign_player"),"Player",choices=NULL),
              shiny::uiOutput(ns("sign_status")),
              shiny::uiOutput(ns("sign_years_control")),
              shiny::numericInput(ns("sign_salary"),"Final contract salary ($m)",value=1.1,min=1.1,step=.01)),
            shiny::conditionalPanel("input.action === 'Trade For'", ns=ns,
              shiny::selectizeInput(ns("incoming"),"Player",choices=NULL),
              NULL),
            shiny::conditionalPanel("input.action === 'Cash Trade'", ns=ns,
              shiny::selectInput(ns("cash_partner"),"Trade partner",choices=NULL),
              shiny::uiOutput(ns("cash_range")),
              shiny::radioButtons(ns("cash_direction"),NULL,c("Receive cash"="receive","Send cash"="send"),inline=TRUE),
              shiny::numericInput(ns("cash_amount"),"Cash amount ($m)",value=.01,min=.01,step=.01),
              shiny::checkboxInput(ns("cash_qualifies"),"Both sides include an SD-minimum contract or a Round 1/2 pick",FALSE),
              shiny::uiOutput(ns("cash_preview")),
              shiny::helpText("Current-year cap space, in $0.01m increments. Positive net cash means received; negative means sent.")),
            shiny::uiOutput(ns("move_controls")),
            shiny::uiOutput(ns("move_preview")),
            shiny::uiOutput(ns("add_control"))),
          shiny::div(class="cap-move-queue",
            shiny::tags$h4("Roster Scenario"),
            shiny::uiOutput(ns("moves")),
            shiny::div(class="cap-move-buttons",
              shiny::actionButton(ns("reset"), "Clear Scenario")),
            shiny::div(class="cap-scenario-projection",shiny::uiOutput(ns("projection")))))))))
    ))
  )
}

cap_manager_server <- function(id, players_data, snapshots_data, history_data, season, active, as_of=function() Sys.time()) {
  shiny::moduleServer(id, function(input, output, session) {
    ns <- session$ns
    data <- shiny::reactiveVal(cap_load_cache(season=season))
    error <- shiny::reactiveVal(NULL)
    moves <- shiny::reactiveVal(list())
    move_sequence <- shiny::reactiveVal(0L)
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
      series <- cap_history_series(data(),input$team,input$history_view)
      chart <- cap_history_plot(series,input$history_lines,team()$franchise_cap,data()$league_cap,input$history_view)
      svg <- svglite::svgstring(width=7,height=4.6,standalone=FALSE)
      tryCatch(print(chart),finally=grDevices::dev.off())
      markup <- svg()
      # Browser text inherits the dashboard's Inter webfont, rather than rasterizing a server font.
      markup <- gsub(" textLength='[^']*' lengthAdjust='[^']*'", "", markup)
      document <- xml2::read_xml(as.character(markup))
      points <- xml2::xml_find_all(document,"//*[local-name()='circle']")
      shown <- series[series$series %in% input$history_lines & is.finite(series$value),,drop=FALSE]
      stopifnot(length(points)==nrow(shown))
      for(i in seq_along(points)) {
        label <- sprintf("Week %d | %s (%s) | %s: $%.2fm",shown$week[i],shown$group[i],shown$kind[i],
          if(input$history_view=="space") "Cap space" else "Expenditures",shown$value[i])
        hit <- xml2::xml_add_sibling(points[[i]],"circle",cx=xml2::xml_attr(points[[i]],"cx"),
          cy=xml2::xml_attr(points[[i]],"cy"),r="7",fill="transparent",stroke="none",
          style="fill:transparent;stroke:none;opacity:0;pointer-events:all",
          `pointer-events`="all",tabindex="0",`aria-label`=label)
        xml2::xml_add_child(hit,"title",label)
      }
      markup <- as.character(xml2::xml_root(document))
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
    })
    # Selection changes must not rebuild their own picker. A team roster is
    # small enough to keep its searchable choices entirely in the browser.
    available_players <- shiny::reactive({
      available <- roster()
      used <- vapply(moves(), function(m) m$player_id, "")
      available <- available[!available$player_id %in% used,]
      if(identical(input$action,"Extend") && nrow(available)) {
        eligible <- vapply(seq_len(nrow(available)),function(i) {
          p <- tryCatch(player_context(available[i,,drop=FALSE]),error=function(e) NULL)
          !is.null(p) && length(cap_extension_years(p,extension_week_current))>0
        },logical(1))
        available <- available[eligible,,drop=FALSE]
      }
      cap_canonical_roster(available)
    })
    shiny::observeEvent(available_players(), {
      available <- available_players()
      shiny::updateSelectizeInput(session,"player",choices=cap_player_choice_labels(available,season),
        selected=if(length(input$player)==1 && input$player %in% available$player_id) input$player else head(available$player_id, 1), server=FALSE)
    })
    selected <- shiny::reactive({
      shiny::req(input$player)
      row <- roster()[roster()$player_id==input$player,,drop=FALSE]
      shiny::req(nrow(row)==1)
      row
    })
    player_context <- function(row) {
      p <- players_data()
      p <- p[p$conference==row$conference & p$player_id==row$player_id,,drop=FALSE]
      if(nrow(p)!=1) return(NULL)
      for (field in c("prev_salary","prev_years","contract","franchise","roster_status")) p[[field]] <- row[[field]]
      # Current ownership/contract comes from live MFL, never an older weekly roster.
      ext_player_context(p, snapshots_data(), tibble::tibble(), history_data(),
        extension_week_default, season, historical=FALSE)
    }
    context <- shiny::reactive(player_context(selected()))
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
        paste0(names(cap_player_choice_labels(candidates,season))," - ",candidates$franchise)),
        selected=if(length(input$incoming)==1 && input$incoming %in% candidates$player_id) input$incoming else head(candidates$player_id,1),server=FALSE)
      partners <- sort(unique(data()$roster$franchise[data()$roster$conference==roster()$conference[1] &
        data()$roster$franchise!=input$team]))
      shiny::updateSelectInput(session,"cash_partner",choices=partners,
        selected=if(length(input$cash_partner)==1 && input$cash_partner %in% partners) input$cash_partner else head(partners,1))
    })
    signing_limit <- shiny::reactive({
      shiny::invalidateLater(60000,session)
      cap_signing_max_years(season,as_of())
    })
    signing_candidates <- shiny::reactive({
      shiny::req(input$team)
      pool <- data()$free_agents
      if(is.null(pool)) return(data.frame(player_id=character(),player=character(),conference=character()))
      used <- vapply(moves(),function(m)m$player_id,character(1))
      pool <- pool[pool$conference==roster()$conference[1] & !pool$player_id %in% used,,drop=FALSE]
      pool[order(pool$player),,drop=FALSE]
    })
    shiny::observeEvent(signing_candidates(), {
      pool <- signing_candidates()
      shiny::updateSelectizeInput(session,"sign_player",choices=stats::setNames(pool$player_id,pool$player),
        selected=if(length(input$sign_player)==1 && input$sign_player %in% pool$player_id) input$sign_player else head(pool$player_id,1),server=TRUE)
    })
    output$sign_status <- shiny::renderUI({
      if(is.null(data()$free_agents)) shiny::div(role="status","Free-agent list unavailable. Use Refresh ADL Rosters to retry.")
    })
    output$sign_years_control <- shiny::renderUI({
      if(signing_limit()==1L) return(NULL)
      shiny::numericInput(ns("sign_years"),"Contract years (including this season)",value=1,min=1,max=signing_limit(),step=1)
    })
    output$move_controls <- shiny::renderUI({
      if(is.null(input$action)) return(NULL)
      if(input$action %in% c("Sign Player","Trade For","Cash Trade")) return(NULL)
      row <- selected()
      if(identical(input$action,"Trade Away")) return(NULL)
      if(identical(input$action,"Extend")) {
        p <- context()
        years <- if(is.null(p)) integer() else cap_extension_years(p, extension_week_current)
        if(!length(years)) return(shiny::div(role="status", if(is.null(p))
          "EXT data is not published for this player yet." else if(extension_week_current>16)
          "The in-season extension window is closed." else p$eligibility_note))
        tagList(shiny::selectInput(ns("years"),"Years to add",choices=years,selected=years[1]),
          shiny::helpText(paste("EXT week",extension_week_default)),
          if(has_available_fifth_year_option(p) && !has_exercised_fifth_year_option(p))
            shiny::checkboxInput(ns("five_year"),"Include available fifth-year option",FALSE))
      } else {
        tagList(shiny::checkboxInput(ns("claimed"),"Player is claimed on waivers (no penalty)",FALSE),
          shiny::checkboxInput(ns("accelerate"),paste0("Accelerate ",season+1," cap penalty into ",season,"."),FALSE),
          if(format(Sys.Date(),"%m-%d")<"07-01") shiny::checkboxInput(ns("july_tender"),"Use an available July 1 Tender",FALSE))
      }
    })
    preview <- shiny::reactive({
      if(identical(input$action,"Sign Player")) {
        salary <- input$sign_salary
        pool <- signing_candidates()
        if(length(input$sign_player)!=1) return(NULL)
        player <- pool[pool$player_id==input$sign_player,,drop=FALSE]
        if(nrow(player)!=1 || length(salary)!=1 || !is.finite(salary) || salary<cap_vet_min(season) || abs(salary-round_salary(salary))>1e-8) return(NULL)
        years <- if(signing_limit()==1L) 1L else input$sign_years %||% 1L
        if(length(years)!=1 || !is.finite(years) || years<1 || years>signing_limit() || years!=floor(years)) return(NULL)
        return(list(player_id=player$player_id,player=player$player,action="Sign Player",
          delta=salary,paid_delta=1,years_delta=years,next_year=0,penalty=0,cash_net=0,contract_salary=salary,contract_years=years,
          detail=paste("Sign at",money(salary),"for",years,if(years==1) "year" else "years","- adds one paid player")))
      }
      if(identical(input$action,"Trade For")) {
        p <- trade_candidates()
        p <- p[p$player_id==input$incoming,,drop=FALSE]
        if(nrow(p)!=1) return(NULL)
        return(list(player_id=p$player_id,player=p$player,action="Trade For",delta=p$prev_salary,
          paid_delta=1,years_delta=p$prev_years,next_year=0,penalty=0,cash_net=0,
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
        return(list(player_id=paste0("cash:",move_sequence()+1L),player=paste(input$cash_partner,"cash"),
          action="Cash Trade",delta=-net,paid_delta=0,next_year=0,penalty=0,cash_net=net,partner=input$cash_partner,
          detail=paste(if(net>0) "Receive" else "Send",money(amount),if(net>0) "from" else "to",input$cash_partner)))
      }
      row <- selected()
      used <- vapply(moves(),function(m) m$player_id,"")
      if(row$player_id %in% used) return(NULL)
      if(identical(input$action,"Trade Away")) {
        paid <- as.integer(cap_paid(row))
        return(list(player_id=row$player_id,player=row$player,action="Trade Away",
          delta=if(paid) -row$prev_salary else 0,paid_delta=-paid,years_delta=-row$prev_years,next_year=0,penalty=0,cash_net=0,
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
          delta=delta,years_delta=result$final_years-row$prev_years,penalty=0,next_year=0,vacancy=0,paid_delta=0,
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
          penalty=penalty$current,next_year=penalty$next_year,paid_delta=-paid,years_delta=-row$prev_years,vacancy=0,
          detail=paste(season,"penalty",money(penalty$current),paste0("\u2022 ",season+1," penalty"),money(penalty$next_year)))
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

    cash_range <- shiny::reactive({
      shiny::req(input$cash_partner)
      partner <- data()$teams[data()$teams$franchise==input$cash_partner,,drop=FALSE]
      shiny::req(nrow(partner)==1)
      own <- cash_status()
      prior <- sum(vapply(moves(),function(m)if(identical(m$partner,input$cash_partner)) -(m$cash_net %||% 0) else 0,numeric(1)))
      other <- cap_cash_status(partner$net_cash_received,prior,data()$league_cap)
      list(send=max(0,min(own$can_send,other$can_receive)),
        receive=max(0,min(own$can_receive,other$can_send)),own=own,other=other)
    })
    output$cash_range <- shiny::renderUI({
      r <- cash_range()
      if(!r$own$valid || !r$other$valid) return(shiny::div(class="alert alert-warning","Cash range unavailable: review the current cash balances and queued moves."))
      shiny::div(class="cap-cash-range",
        shiny::tags$strong(paste(input$team,"and",input$cash_partner,"available cash trade")),
        shiny::div(class="cap-cash-range-values",
          shiny::div(shiny::tags$small("Send up to"),shiny::tags$strong(paste0("-",money(r$send)))),
          shiny::div(class="cap-cash-zero","0"),
          shiny::div(shiny::tags$small("Receive up to"),shiny::tags$strong(paste0("+",money(r$receive))))),
        shiny::div(class="cap-cash-range-track",`aria-hidden`="true"),
        shiny::tags$p("Negative = send cash. Positive = receive cash. Includes queued moves and both teams' limits."),
        shiny::tags$p(paste(input$team,"net:",money(r$own$net),"|",input$cash_partner,"net:",money(r$other$net),
          "| Each team's limit: +/-",money(r$own$limit))))
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
      if(identical(input$action,"Sign Player")) return(NULL)
      p <- preview()
      if(is.null(p)) return(NULL)
      vacancy <- round_salary(vacancy_delta(c(moves(),list(p)))-vacancy_delta(moves()))
      shiny::div(class="cap-move-preview",shiny::tags$p(p$detail),
        if(!identical(input$action,"Extend")) shiny::tags$p(paste("Added empty-slot spending:",money(vacancy),"per remaining week.")),
        shiny::tags$strong(paste("Net spending change:",money(round_salary(p$delta+vacancy)))))
    })
    output$add_control <- shiny::renderUI({
      if(is.null(preview())) return(NULL)
      shiny::actionButton(ns("add"),"Add Transaction",class="btn-primary")
    })
    shiny::observeEvent(input$add, {
      p <- preview(); shiny::req(p)
      move_sequence(move_sequence()+1L)
      p$queue_id <- as.character(move_sequence())
      moves(c(moves(),list(p)))
    })
    shiny::observeEvent(input$reset,moves(list()))
    shiny::observeEvent(input$remove_move, {
      keys <- vapply(seq_along(moves()),function(i)moves()[[i]]$queue_id %||% as.character(i),character(1))
      i <- match(as.character(input$remove_move),keys)
      if(length(i)==1 && !is.na(i)) moves(moves()[-i])
    })
    metric_text <- function(value) {
      if(!is.character(value) || length(value)!=1) return(value)
      value <- gsub(" (", "\n(", value, fixed=TRUE)
      value <- gsub("ADL Salary Cap + ", "ADL Salary Cap +\n", value, fixed=TRUE)
      lines <- strsplit(value,"\n",fixed=TRUE)[[1]]
      shiny::tagList(lapply(seq_along(lines),function(i)
        shiny::tagList(if(i>1) shiny::tags$br(),lines[i])))
    }
    metric <- function(label,value,note=NULL,change=NULL,lower_better=FALSE) {
      shiny::div(class="cap-metric",shiny::tags$span(
        if(grepl("^Current [0-9]{4} Rollover \\(Cap Space\\)$",label)) shiny::tags$span(style="white-space:nowrap;display:inline;font-size:inherit;color:inherit",label) else metric_text(label)),
        shiny::tags$strong(if(is.na(value)) "\u2014" else money(value)),
        if(!is.null(change) && is.finite(change)) shiny::tags$small(
          class=paste("cap-change",if(change==0) "neutral" else if((change<0)==lower_better) "favorable" else "unfavorable"),
          paste0(if(change>0) "+" else if(change<0) "-" else "",money(abs(change))," vs current")),
        if(!is.null(note)) shiny::tags$small(class="cap-metric-note",metric_text(note)))
    }
    output$current <- shiny::renderUI({
      shiny::req(data(),input$team)
      c <- current(); b <- baseline(); cash <- cash_status()
      cash_trades <- data()$cash_trades
      if(!is.null(cash_trades)) cash_trades <- cash_trades[cash_trades$franchise==input$team,,drop=FALSE]
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
        shiny::div(class="cap-equation cap-equation-projected",
          metric(paste(season,"Franchise Cap"),team()$franchise_cap,note=paste(
            money(data()$league_cap),"ADL Salary Cap +",money(round_salary(team()$franchise_cap-data()$league_cap)),season-1,"Cap Rollover")),
          shiny::div(class="cap-equation-sign",`aria-label`="minus","\u2212"),
          metric("Projected Seasonlong Expenditures (at current spending)",b$projected_average,
            note=paste(c(
              if(b$weeks>0) paste0("Weeks 1-",b$weeks,": ",money(b$average)),
              if(b$remaining>0) paste0("Weeks ",b$weeks+1,"-17: ",money(c$spending))),collapse="\n")),
          shiny::div(class="cap-equation-sign",`aria-label`="equals","=",
            if(is.finite(b$projected_average) && team()$franchise_cap-b$projected_average > data()$league_cap*.1)
              shiny::tags$small("after rollover cap")),
          metric(paste("Projected",season+1,"Rollover (at current spending)"),b$projected_rollover,
            note=paste("Maximum rollover:",money(data()$league_cap*.1),"(10% of ADL Salary Cap)"))),
      shiny::div(class="cap-metrics",
        metric("Current Expenditures",c$spending,note=sprintf(
          "Salaries: %s \u2022 Empty Roster Slots: $%.2f (%d paid players) \u2022 Adjustments: %s",
          money(c$roster),c$vacancy,c$paid,money(c$adjustment))),
        metric("Effective Cap Space",b$effective,note=paste("Additional allowable weekly spending to remain under",season,"Franchise Cap.")),
        metric("Net Cash Charge via Trades",-team()$net_cash_received,
          note=shiny::tagList(metric_text(paste0("Min Allowed: -",money(cash$limit)," | Max Allowed: ",money(cash$limit)," (5% of ADL Salary Cap)")),
            if(!is.null(cash_trades) && nrow(cash_trades)) shiny::div(class="cap-cash-ledger",
              lapply(seq_len(nrow(cash_trades)),function(i) {
                entry <- cash_trades[i,]
                date <- if(is.na(entry$date)) "Date unavailable" else entry$date
                partner <- if(is.na(entry$partner)) "Partner unavailable" else entry$partner
                shiny::div(paste(date,if(entry$amount>0) paste("Sent",partner,money(entry$amount)) else paste(partner,"sent",money(abs(entry$amount))),
                  paste0("[",if(entry$amount>=0) "+" else "\u2212",money(abs(entry$amount)),"]")))
              }))))))
    })

    scenario <- shiny::reactive({
      move_delta <- sum(vapply(moves(),function(m)m$delta,numeric(1)))
      adjustment_delta <- round_salary(sum(vapply(moves(),function(m)(m$penalty %||% 0)-(m$cash_net %||% 0),numeric(1))))
      salary_delta <- round_salary(move_delta-adjustment_delta)
      slot_delta <- vacancy_delta(moves())
      components <- list(roster=round_salary(current()$roster+salary_delta),
        vacancy=round_salary(current()$vacancy+slot_delta),
        adjustment=round_salary(current()$adjustment+adjustment_delta),
        salary_delta=salary_delta,vacancy_delta=slot_delta,adjustment_delta=adjustment_delta)
      delta <- move_delta+slot_delta
      forward <- round_salary(components$roster+components$vacancy+components$adjustment)
      shiny::validate(shiny::need(forward>=0,"The resulting scenario expenditures cannot be negative."))
      i <- match(input$team,data()$teams$franchise)
      p <- cap_projection(data()$finals[i,],team()$franchise_cap,data()$league_cap,forward)
      c(p,list(forward=forward,delta=round_salary(delta),components=components))
    })
    output$projection <- shiny::renderUI({
      shiny::req(data(),input$team)
      b <- baseline(); s <- scenario()
      component_change <- function(value) paste0(if(value>0) "+" else if(value<0) "\u2212" else "",money(abs(value)))
      components <- s$components
      tagList(shiny::div(class="cap-metrics",
        metric("Current Expenditures (scenario)",s$forward,
          note=paste0("Salaries: ",money(components$roster)," (",component_change(components$salary_delta),")\n",
            "Empty Roster Slots: ",money(components$vacancy)," (",component_change(components$vacancy_delta),")\n",
            "Adjustments: ",money(components$adjustment)," (",component_change(components$adjustment_delta),")"),
          change=round_salary(s$forward-current()$spending),lower_better=TRUE),
        metric("Projected Seasonlong Expenditures (scenario)",s$projected_average,
          note=paste(c(if(s$weeks) paste0("Weeks 1-",s$weeks,": ",money(s$average)),
            if(s$remaining>0) paste0("Weeks ",s$weeks+1,"-17: ",money(s$forward))),collapse="\n"),
          change=round_salary(s$projected_average-b$projected_average),lower_better=TRUE),
        metric(paste("Projected",season+1,"Rollover (scenario)"),s$projected_rollover,
          note=paste("Maximum rollover:",money(data()$league_cap*.1),"(10% of ADL Salary Cap)"),
          change=round_salary(s$projected_rollover-b$projected_rollover))),
        if(s$remaining==0) shiny::div(class="alert alert-info","All 17 weeks are recorded. Transactions cannot change this year's rollover."),
        if(s$projected_rollover<0) shiny::div(class="alert alert-warning",role="status","This scenario projects spending above the franchise cap."),
        shiny::tags$p(paste("Scenario transactions change current roster spending by",money(s$delta),"including",money(vacancy_delta(moves())),
          "in empty-slot charges. Added next-year penalties:",money(sum(vapply(moves(),function(m)m$next_year,numeric(1)))))))
    })
    output$weekly_ledger <- shiny::renderUI({
      shiny::req(data(),input$team)
      ledger <- data()$ledger
      if(is.null(ledger) || !nrow(ledger)) return(shiny::tags$p("Weekly Ledger is unavailable. Use Refresh ADL Rosters to retry."))
      ledger <- ledger[ledger$franchise==input$team,,drop=FALSE]
      ledger <- ledger[order(ledger$week),,drop=FALSE]
      if(!nrow(ledger)) return(shiny::tags$p("No completed weekly snapshots are recorded yet."))
      fields <- c("A","IR","S","TE","Yrs","Paid","Vac$","RostSal","Adj","Corr","Final")
      definitions <- c("Active roster players","Injured-reserve players","Suspended/holdout players",
        "Non-suspended/non-holdout taxi players","Contract years excluding IR and suspended/holdout taxi",
        "Paid players, excluding suspended/holdout taxi",
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
      illegal <- cap_ledger_illegal(ledger[["Ill?"]])
      shiny::tagList(shiny::div(class="cap-ledger-scroll",
        shiny::tags$table(class="table table-striped cap-ledger",
          shiny::tags$thead(shiny::tags$tr(shiny::tags$th("Week",scope="col"),
            lapply(seq_along(fields),function(i) shiny::tags$th(fields[i],title=definitions[i],scope="col")))),
          shiny::tags$tbody(lapply(seq_len(nrow(ledger)),function(i) shiny::tags$tr(class=if(illegal[i]) "cap-ledger-illegal" else NULL,
            shiny::tags$th(paste("Week",ledger$week[i]),scope="row"),
            lapply(fields,function(field) shiny::tags$td(format_cell(ledger[[field]][i],field)))))),
          shiny::tags$tfoot(shiny::tags$tr(shiny::tags$th(shiny::tags$strong("Average"),scope="row"),
            lapply(fields,function(field) shiny::tags$td(shiny::tags$strong(format_cell(cumulative[[field]],field,average=TRUE)))))))),
        shiny::tags$p(class="cap-source","Hover over a column heading for its definition."),
        shiny::tags$p(class="cap-source","Illegal rosters at snapshot displayed in red."))
    })
    next_outlook <- shiny::reactive({
      shiny::req(input$team)
      tryCatch(cap_next_outlook(data(),input$team,moves(),scenario()$projected_rollover),error=identity)
    })
    output$next_season <- shiny::renderUI({
      n <- next_outlook()
      if(inherits(n,"error")) return(shiny::div(class="alert alert-warning",conditionMessage(n)))
      b <- cap_next_outlook(data(),input$team,list(),baseline()$projected_rollover)
      tagList(
        shiny::div(class="cap-equation",
          metric(paste(n$year,"projected franchise cap"),n$franchise_cap,note=paste(money(n$league_cap),"ADL Salary Cap +",money(n$rollover),n$year-1,"Cap Rollover")),
          shiny::div(class="cap-equation-sign",`aria-label`="minus","\u2212"),
          metric(paste(n$year,"projected expenditures"),n$spending,change=round_salary(n$spending-b$spending),lower_better=TRUE),
          shiny::div(class="cap-equation-sign",`aria-label`="equals","="),
          metric(paste(n$year,"projected cap space"),n$space,change=round_salary(n$space-b$space))),
        shiny::div(class="cap-metrics",
        metric(paste(n$year,"projected ADL league cap"),n$league_cap),
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
    output$next_roster <- shiny::renderUI({
      n <- next_outlook(); shiny::validate(shiny::need(!inherits(n,"error"),"Next-season roster unavailable."))
      original <- data()$next_season$roster
      n$departures <- original[original$franchise==input$team & !original$player_id %in% n$roster$player_id,,drop=FALSE]
      cap_next_roster_table(n)
    })
    output$moves <- shiny::renderUI({
      if(!length(moves())) return(NULL)
      tagList(shiny::tags$ol(class="cap-queue",lapply(seq_along(moves()),function(i) {
        m <- moves()[[i]]
        vacancy <- vacancy_delta(moves()[seq_len(i)])-if(i>1) vacancy_delta(moves()[seq_len(i-1)]) else 0
        shiny::tags$li(
          shiny::tags$button(type="button",class="cap-move-remove",title="Remove move",
            `aria-label`=paste("Remove",m$action,m$player),
            onclick=sprintf("Shiny.setInputValue(%s,%s,{priority:'event'})",
              jsonlite::toJSON(ns("remove_move"),auto_unbox=TRUE),
              jsonlite::toJSON(m$queue_id %||% as.character(i),auto_unbox=TRUE)),"\u00d7"),
          shiny::tags$strong(cap_scenario_move_title(m)),shiny::tags$p(m$detail),
          shiny::tags$small(paste("Net spending change (with slots):",money(round_salary(m$delta+vacancy)))))
      })), shiny::div(class="cap-queue-total cap-scenario-deltas",
        shiny::tags$strong(paste0("Expenditures ",if(scenario()$delta>=0) "+" else "",money(scenario()$delta))),
        shiny::tags$strong({years <- sum(vapply(moves(),function(m)m$years_delta %||% 0,numeric(1)))
          paste0("Years ",if(years>=0) "+" else "",years)})))
    })
  })
}

cap_canonical_roster <- function(roster) {
  positions <- c("QB","RB","WR","TE","PK","PN","DT","DE","LB","CB","S")
  position <- sub(".* ","",roster$player)
  roster[order(match(position,positions),roster$player,na.last=TRUE),,drop=FALSE]
}

cap_next_roster_table <- function(n) {
  roster <- n$roster
  retained <- roster[roster$next_years>0,,drop=FALSE]
  canonical <- cap_canonical_roster
  retained <- canonical(retained)
  lost <- roster[roster$next_years==0,,drop=FALSE]
  if(!is.null(n$departures) && nrow(n$departures)) lost <- dplyr::bind_rows(lost,n$departures)
  if(nrow(lost)) {
    lost$next_years <- 0
    lost$next_salary <- round_salary(lost$prev_salary*1.1)
    lost$next_status <- "Not retained"
    lost <- canonical(lost)
  }
  draft <- retained$origin=="Draft reserve"
  salary <- function(x) sprintf("$%.2f",x)
  section <- function(label) shiny::tags$tr(class="cap-roster-section",shiny::tags$th(label,colspan=4,scope="colgroup"))
  rows <- function(r) lapply(seq_len(nrow(r)),function(i) {
    contract <- r$contract[i]
    if(is.na(contract) || !nzchar(contract)) contract <- paste(n$year,"Draft reserve")
    if(r$next_status[i]=="ERFA tag assumed") contract <- paste(n$year,"ERFA (assumed)")
    shiny::tags$tr(
      shiny::tags$td(class="cap-roster-player",r$player[i]),
      shiny::tags$td(salary(r$next_salary[i])),shiny::tags$td(r$next_years[i]),
      shiny::tags$td(contract,
        if(r$next_status[i] %in% c("Exercised fifth-year option","Scenario extension","Scenario acquisition","Scenario signing"))
          shiny::tags$small(class="cap-roster-assumption",r$next_status[i])))
  })
  total <- function(label,value,years=NULL,contract=NULL) shiny::tags$tr(
    shiny::tags$th(label,scope="row"),shiny::tags$td(value),shiny::tags$td(years),shiny::tags$td(contract))
  shiny::tagList(shiny::div(class="cap-roster-scroll",
    shiny::tags$table(class="cap-roster-table",`aria-label`=paste(n$year,"projected ADL roster"),
      shiny::tags$thead(shiny::tags$tr(lapply(c("Player","Salary","Years","Contract"),function(label) shiny::tags$th(label,scope="col")))),
      shiny::tags$tbody(
        section("Projected roster"),rows(retained[!draft,,drop=FALSE]),
        if(any(draft)) rows(retained[draft,,drop=FALSE])),
      shiny::tags$tfoot(
        total(paste(n$paid,"TOTAL PLAYERS"),salary(n$salaries),sum(retained$next_years)),
        total("Salary Adjustments:",salary(n$official_adjustments+n$scenario_penalties)),
        total(paste0("Empty Roster Slots (",n$empty,"):"),salary(n$vacancy),
          contract=paste0(n$year," veteran minimum: $",sprintf("%.2f",cap_vet_min(n$year)),"m per slot")),
        total("TOTAL:",salary(n$spending)),
        total("SALARY CAP:",salary(n$franchise_cap)),
        total("CAP ROOM AVAILABLE:",salary(n$space))))),
    shiny::tags$p(class="cap-source","ERFA tags signed by default and draft picks assumed to be retained."),
    shiny::tags$p(class="cap-source","Draft projections use the current forecast from the ",
      shiny::tags$a(href="https://themathninja.github.io/ADL-GM-Dashboard/playoff-picture/",target="_blank",rel="noopener noreferrer","Playoff module"),"."),
    shiny::tags$h4("Players Lost",class="cap-roster-heading"),
    if(nrow(lost)) shiny::tagList(
      shiny::div(class="cap-roster-scroll",shiny::tags$table(class="cap-roster-table cap-lost-roster",`aria-label`="Players Lost",
        shiny::tags$thead(shiny::tags$tr(lapply(c("Player","Salary","Years","Contract"),function(label) shiny::tags$th(label,scope="col")))),
        shiny::tags$tbody(rows(lost)))))
    else shiny::tags$p(class="cap-source","No players lost in this projection."))
}

cap_player_choice_labels <- function(roster,season) {
  if(!nrow(roster)) return(stats::setNames(character(),character()))
  labels <- vapply(seq_len(nrow(roster)),function(i) {
    row <- roster[i,,drop=FALSE]
    guarantee <- cap_guarantee(row,season)
    if(is.na(guarantee)) guarantee <- "guarantee unavailable"
    sprintf("%s [$%.2fm (%s), %s %s, %s]",row$player,row$prev_salary,guarantee,
      row$prev_years,if(row$prev_years==1) "year" else "years",row$contract)
  },character(1))
  stats::setNames(roster$player_id,labels)
}

cap_scenario_move_title <- function(move) {
  action <- move$action
  if(grepl("^Extend ",action)) {
    years <- suppressWarnings(as.integer(sub("^Extend \\+ ([0-9]+) years$","\\1",action)))
    if(length(years)==1 && !is.na(years)) action <- paste("Extend",years,if(years==1) "year" else "years")
  }
  paste0("[",action,"] ",move$player)
}









