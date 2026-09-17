comp_tracker_ui <- function(id) {
  ns <- NS(id)
  tagList(tags$link(rel = "stylesheet", href = "comp-tracker.css?v=watch-6"),
    div(class = "comp-tracker",
      div(class = "gm-conference-toggle", radioButtons(ns("conference"), tags$span(class = "visually-hidden", "Conference"),
        choices = c("NFC", "AFC"), selected = "NFC", inline = TRUE)),
      div(class = "comp-toolbar", uiOutput(ns("team_selector")), downloadButton(ns("export"), "Download team events")),
      uiOutput(ns("dashboard"))))
}

comp_tracker_server <- function(id, path = "data/comp_picks.rds") {
  moduleServer(id, function(input, output, session) {
    branding <- reactiveFileReader(60000, session, "data/ext_candidates.csv", function(p) {
      x <- readr::read_csv(p, show_col_types = FALSE)
      franchises <- unique(x[c("franchise_name", "franchise")])
      # MFL uses JAC for NFL players; ADL's franchise code is JAX.
      franchises$player_team <- ifelse(franchises$franchise == "JAX", "JAC", franchises$franchise)
      visuals <- unique(x[c("player_team", "team_logo_espn", "team_color", "team_color2")])
      visuals <- visuals[!duplicated(visuals$player_team), ]
      dplyr::left_join(franchises, visuals, by = "player_team")
    })
    snapshot <- reactiveFileReader(60000, session, path, function(p) if (file.exists(p)) readRDS(p) else NULL)
    output$team_selector <- renderUI({
      s <- snapshot(); req(s, input$conference)
      teams <- s$teams[s$teams$conference == input$conference, ]
      # Match EXT's arrange(franchise): alphabetical ADL abbreviations,
      # while keeping full team names as the visible choice labels.
      codes <- branding()[c("franchise_name", "franchise")]
      teams <- dplyr::left_join(teams, codes, by = "franchise_name") |>
        dplyr::arrange(franchise, franchise_name)
      selected <- isolate(input$team)
      if (is.null(selected) || !selected %in% teams$franchise_id) selected <- teams$franchise_id[[1]]
      selectInput(session$ns("team"), tags$span(class = "visually-hidden", "Team"), setNames(teams$franchise_id,
        teams$franchise_name), selected = selected)
    })
    output$export <- downloadHandler(filename = function() paste0("comp-picks-", input$team, ".csv"),
      content = function(file) { s <- snapshot(); req(s, input$team); write.csv(s$events[s$events$franchise_id == input$team, ], file, row.names = FALSE) })
    output$dashboard <- renderUI({
      s <- snapshot()
      if (is.null(s)) return(div(class = "comp-empty", "The compensatory picks snapshot is unavailable. Please check back after the next data refresh."))
      req(input$team)
      team <- s$teams[s$teams$franchise_id == input$team, ]; req(nrow(team) == 1)
      brand <- branding()
      brand <- brand[match(team$franchise_name, brand$franchise_name), ]
      valid_color <- function(x, fallback) if (length(x) == 1 && !is.na(x) && grepl("^#[0-9a-fA-F]{6}$", x)) x else fallback
      primary <- valid_color(brand$team_color, "#203d5c")
      secondary <- valid_color(brand$team_color2, "#d65757")
      contrast_text <- function(color) {
        rgb <- as.numeric(grDevices::col2rgb(color)) / 255
        linear <- ifelse(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055)^2.4)
        luminance <- sum(linear * c(0.2126, 0.7152, 0.0722))
        if ((luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05)) "#000000" else "#FFFFFF"
      }
      banner_style <- paste0("--comp-primary:", primary, ";--comp-secondary:", secondary,
        ";--comp-primary-text:", contrast_text(primary), ";--comp-secondary-text:", contrast_text(secondary), ";")
      ev <- s$events[s$events$franchise_id == input$team, ]
      losses <- ev[ev$cfa_event == "LOST", ]; gains <- ev[ev$cfa_event == "GAINED", ]
      below <- s$below_threshold_events
      if (is.null(below)) below <- ev[0, ]
      below <- below[below$franchise_id == input$team, ]
      below <- below[order(-below$win_bid, below$player_name), ]
      below_resigned <- below[below$cfa_event == "RE-SIGNED", ]
      below <- below[below$cfa_event %in% c("LOST", "GAINED"), ]
      below_lost <- below[below$cfa_event == "LOST", ]
      below_gained <- below[below$cfa_event == "GAINED", ]
      losses <- losses[order(-losses$win_bid, losses$player_name), ]
      gains <- gains[order(-gains$win_bid, gains$player_name), ]
      pairs <- s$cancel$cancels[s$cancel$cancels$franchise_id == input$team, ]
      board <- s$conferences[[team$conference]]
      picks <- board$picks[!is.na(board$picks$franchise_id) & board$picks$franchise_id == input$team, ]
      cash <- function(x) sprintf("$%.2fm", x)
      threshold_at <- function(p) as.numeric(sub("$", "", s$thresholds$thresholds$Salary[s$thresholds$thresholds$`ADL Percentile` == p], fixed = TRUE))
      third_min <- threshold_at(90)
      fourth_min <- threshold_at(80)
      fifth_min <- s$thresholds$meta$cfa_cutoff_m
      threshold_tile <- function(round, amount, detail) div(class = paste0("comp-threshold comp-threshold-", round),
        span(paste("ROUND", round)), strong(paste0(cash(amount), "+")), tags$small(detail))
      badge <- function(text, cls = "") span(class = paste("comp-badge", cls), text)
      metric <- function(value, label, detail) div(class = "comp-metric", span(label), strong(value), tags$small(detail))
      person <- function(id, name, detail, status = NULL) {
        photo <- s$photos[match(as.character(id), s$photos$player_id), ]
        url <- photo$player_headshot[[1]]
        div(class = "comp-person",
          div(class = "comp-avatar", span(substr(name, 1, 1)),
            if (!is.na(url) && nzchar(url)) tags$img(src = url, alt = "", loading = "lazy", onerror = "this.style.display='none'")),
          div(class = "comp-person-copy", strong(nflreadr::clean_player_names(name)), tags$small(detail)), status)
      }
      event_cards <- function(rows, type) {
        if (!nrow(rows)) return(div(class = "comp-empty", paste("No qualifying", tolower(type), "players.")))
        tagList(lapply(seq_len(nrow(rows)), function(i) {
          r <- rows[i, ]; status <- "Does not cancel a loss"
          if (type == "LOST") {
            status <- if (r$player_id %in% pairs$lost_player_id) "Offsetting" else if (r$player_id %in% picks$player_id) "Projected pick" else if (r$player_id %in% board$team_trim$player_id[board$team_trim$franchise_id == input$team]) "Team limit" else "Conference limit"
          } else if (type == "GAINED" && r$player_id %in% pairs$gained_player_id) status <- "Cancels a loss"
          else if (type == "RE-SIGNED") status <- "No impact"
          person(r$player_id, r$player_name, paste(cash(r$win_bid), paste0("Round ", r$comp_round), r$acquired, r$date, sep = " \u00b7 "), badge(status))
        }))
      }
      round_picks <- function(round) {
        rows <- picks[picks$comp_round == round, ]
        div(class = paste("comp-round", paste0("comp-r", round)),
          div(class = "comp-round-title", span(paste("ROUND", round)), strong(nrow(rows))),
          if (!nrow(rows)) p("No projected picks") else tagList(lapply(seq_len(nrow(rows)), function(i) {
            r <- rows[i, ]
            if (r$pick_source == "BONUS") div(class = "comp-bonus", strong("Salary-loss bonus"), p(paste(cash(r$win_bid), "net salary lost")))
            else person(r$player_id, r$player_name, cash(r$win_bid))
          })))
      }
      ledger_player <- function(r) {
        team_abbr <- function(id) {
          name <- s$teams$franchise_name[match(id, s$teams$franchise_id)]
          code <- branding()$franchise[match(name, branding()$franchise_name)]
          if (length(code) && !is.na(code)) code else "Unknown team"
        }
        labels <- s$transaction_labels
        signing <- if (!is.null(labels)) labels[labels$acquired == "auction" &
          labels$player_id == r$player_id & labels$conference == r$conference &
          !is.na(labels$win_bid) & labels$win_bid == r$win_bid, ] else NULL
        if (!is.null(signing) && nrow(signing)) signing <- signing[order(signing$date), ][1, ]
        signed_text <- if (!is.null(signing) && nrow(signing))
          paste("signed by", team_abbr(signing$franchise_id), signing$date) else paste("signed", r$date)
        trade_text <- NULL
        if (r$acquired == "trade") {
          trade <- if (!is.null(labels)) labels[labels$acquired == "trade" &
            labels$player_id == r$player_id & labels$conference == r$conference &
            labels$date == r$date & labels$franchise_id == r$franchise_id, ] else NULL
          partner <- if (!is.null(trade) && nrow(trade)) team_abbr(trade$trade_partner[1]) else "Unknown team"
          trade_text <- paste(if (r$cfa_event == "LOST") "Traded to" else "Traded from", partner, r$date)
        }
        div(class = "comp-ledger-player", person(r$player_id, r$player_name, NULL),
          div(class = "comp-ledger-value", strong(cash(r$win_bid)),
            if (!is.na(r$comp_round)) span(class = paste0("comp-level comp-level-", r$comp_round), paste("Round", r$comp_round))
            else span(class = "comp-level comp-level-inactive", "Below CFA cutoff"),
            tags$small(class = "comp-signed-date", signed_text),
            if (!is.null(trade_text)) tags$small(class = "comp-signed-date", trade_text)))
      }
      ledger_rows <- lapply(seq_len(nrow(losses)), function(i) {
        r <- losses[i, ]
        pair <- pairs[pairs$lost_player_id == r$player_id, ]
        canceled <- nrow(pair) > 0
        projected <- r$player_id %in% picks$player_id
        result <- if (canceled) "Offsetting" else if (projected) paste("Round", r$comp_round, "pick") else if
          (r$player_id %in% board$team_trim$player_id[board$team_trim$franchise_id == input$team]) "Team limit" else "Conference limit"
        div(class = paste("comp-ledger-row", if (canceled) "is-canceled" else if (projected) "is-surviving" else "is-limited"),
          div(class = "comp-lost-cell", ledger_player(r)),
          div(class = "comp-ledger-result", span(class = "comp-ledger-symbol", if (canceled) "\u00d7" else if (projected) "+1" else "\u2014"), span(result)),
          div(class = "comp-won-cell", if (canceled) ledger_player(gains[match(pair$gained_player_id[[1]], gains$player_id), ])
            else div(class = "comp-unmatched", "No offsetting gain")))
      })
      extra_gains <- gains[!gains$player_id %in% pairs$gained_player_id, ]
      extra_rows <- lapply(seq_len(nrow(extra_gains)), function(i) {
        div(class = "comp-ledger-row is-extra",
          div(class = "comp-lost-cell comp-unmatched", "No remaining loss to cancel"),
          div(class = "comp-ledger-result", span(class = "comp-ledger-symbol", "\u2014"), span("Unmatched gain")),
          div(class = "comp-won-cell", ledger_player(extra_gains[i, ])))
      })
      tagList(
        div(class = "comp-hero comp-team-banner", style = banner_style,
          div(class = "comp-team-identity",
            if (!is.na(brand$team_logo_espn) && nzchar(brand$team_logo_espn))
              div(class = "comp-team-logo", tags$img(src = brand$team_logo_espn, alt = paste(team$franchise_name, "logo"), onerror = "this.style.display='none'")),
            h2(team$franchise_name)),
          div(class = "comp-total", strong(nrow(picks))),
          div(class = "comp-team-footer", paste("Projected", s$award_year, "Compensatory Draft Picks"))),
        div(class = "comp-threshold-strip", `aria-label` = "Qualifying auction bid thresholds",
          threshold_tile(3, third_min, "Current 90th percentile ADL salary"),
          threshold_tile(4, fourth_min, "Current 80th percentile ADL salary"),
          threshold_tile(5, fifth_min, "Current 65th percentile ADL salary")),
        div(class = "comp-freshness", paste("Source snapshot:", s$source_at)),
        div(class = "comp-ledger",
          div(class = "comp-ledger-head", div(strong("CFAs Lost"),
            div(class = "comp-ledger-subtitle", span(paste(nrow(losses), if (nrow(losses) == 1) "player" else "players")), span(class = "comp-ledger-salary-total", cash(sum(losses$win_bid))))),
            span(), div(strong("CFAs Gained"),
            div(class = "comp-ledger-subtitle", span(paste(nrow(gains), if (nrow(gains) == 1) "player" else "players")), span(class = "comp-ledger-salary-total", cash(sum(gains$win_bid)))))),
          if (!nrow(losses) && !nrow(gains)) div(class = "comp-empty", "No qualifying losses or gains for this team."),
          ledger_rows, extra_rows,
          if (nrow(below)) tagList(
            div(class = "comp-watch-heading", paste("Following players excluded due to falling below current CFA cutoff", cash(fifth_min))),
            lapply(seq_len(max(nrow(below_lost), nrow(below_gained))), function(i) {
              div(class = "comp-ledger-row is-below-threshold",
                div(class = "comp-lost-cell", if (i <= nrow(below_lost)) ledger_player(below_lost[i, ])),
                div(class = "comp-ledger-result"),
                div(class = "comp-won-cell", if (i <= nrow(below_gained)) ledger_player(below_gained[i, ])))
            })),
          div(class = "comp-ledger-footer",
            div(class = "comp-summary-stat", strong(nrow(losses) - nrow(gains)), span("Net CFAs Lost")),
            div(class = "comp-summary-stat comp-summary-picks", strong(nrow(picks)), span("Projected Picks")),
            div(class = "comp-summary-stat", strong(cash(sum(losses$win_bid) - sum(gains$win_bid))), span("net salary lost")))),
        div(class = "comp-note", "Projection only. Team (4) and conference (16) limits apply after cancellations. Positive Net Salary Lost may add a fifth-round pick for teams with 0 Net CFAs, if conference slots remain. Salary ties, including ties at the conference cutoff, await draft order."),
        div(class = "comp-ledger comp-resigned",
          div(class = "comp-section-head", h3("Re-signed players")),
          {
            resigned <- dplyr::bind_rows(ev[ev$cfa_event == "RE-SIGNED", ], below_resigned)
            resigned <- resigned[order(-resigned$win_bid, resigned$player_name), ]
            if (!nrow(resigned)) div(class = "comp-empty", "No re-signed players.")
            else div(class = "comp-resigned-grid", lapply(seq_len(nrow(resigned)), function(i)
              div(class = paste("comp-resigned-cell", if (is.na(resigned$comp_round[i])) "is-below-threshold" else ""), ledger_player(resigned[i, ]))))
          }),
        div(class = paste("comp-ledger comp-pick-board", paste0("comp-board-", tolower(team$conference))),
          div(class = "comp-section-head", h3(paste("Projected", team$conference, "Compensatory Picks"))),
          div(class = "comp-board-table", tags$table(
            tags$thead(tags$tr(lapply(c("Pick", "Team", "Player / reason", "Salary"), tags$th))),
            tags$tbody(lapply(seq_len(nrow(board$display)), function(i) {
              r <- board$display[i, ]
              logo <- branding()$team_logo_espn[match(r$Team, branding()$franchise_name)]
              tags$tr(class = if (r$Team == team$franchise_name) "is-selected-team" else NULL,
                tags$td(span(class = paste("comp-board-pick", paste0("comp-level-", substr(r$Pick, 1, 1))), r$Pick)),
                tags$td(div(class = "comp-board-team",
                  if (!is.na(logo) && nzchar(logo)) tags$img(src = logo, alt = "", loading = "lazy"),
                  span(r$Team))),
                tags$td(if (is.na(r$Player)) "Draft order" else r$Player),
                tags$td(class = "comp-board-salary", if (is.na(r$Salary)) "\u2014" else r$Salary))
            })))),
          p(class = "comp-board-note", "(t) marks a salary tie. Pick numbers and cutoff outcomes remain provisional until draft order resolves ties.")),
        tags$details(tags$summary("Qualification thresholds & rules"),
          p(strong("Who counts? "), paste("A compensatory free agent (CFA) is a player whose qualifying June auction winning bid amount meets the minimum shown above. This tracker compares your", s$season - 1L, "roster with qualifying acquisitions in", s$season, "within your conference. The auction window is June 1\u201330, Eastern time. Re-signing your own player has no effect; qualifying trade acquisitions count as gains.")),
          p(strong("What determines the round? "), paste("The player's winning bid amount determines their round. Assigning multiple contract years can reduce their salary, but does not change the winning bid amount used here. Currently,", cash(third_min), "or more qualifies for Round 3;", cash(fourth_min), "up to the Round 3 cutoff qualifies for Round 4; and", cash(fifth_min), "up to the Round 4 cutoff qualifies for Round 5. A winning bid exactly on a cutoff earns the higher round. Winning bids below", cash(fifth_min), "do not count.")),
          p(strong("Why can the cutoffs change? "), "They are based on current ADL roster salaries across both conferences: roughly the top 10% for Round 3, top 20% for Round 4, and top 35% for Round 5. ",
            paste("The", s$season, "SD salary base is", cash(s$thresholds$meta$sd_base_m),
              "\u2014 rounded up to", cash(s$thresholds$meta$sd_min_bid_m),
              "for the minimum bid. Adding $100,000 gives an SD-based CFA minimum of", paste0(cash(s$thresholds$meta$sd_plus_100k_m), "."),
              "The actual CFA cutoff is the higher of that minimum and the top-35% salary cutoff, currently", paste0(cash(fifth_min), ".")),
            " Greyed-out ledger rows meet the SD-based minimum but fall below the current CFA cutoff. They do not affect totals, offsets, or picks. The cutoffs update when roster data refreshes; the snapshot date above shows which data you are viewing."),
          p(strong("How do gains offset losses? "), "Each qualifying gain offsets one qualifying loss. The tracker first matches within the same round, then looks to later rounds, and finally earlier rounds. Within those groups, the rules match higher salaries first, except when moving to an earlier round, where lower salaries go first. Matched players appear on the same ledger row; losses left over may earn picks."),
          p(strong("How many picks can a team receive? "), "A team can earn up to four picks from net CFA losses, with 16 compensatory picks available per conference. If space remains, teams with equal numbers of CFAs lost and gained but a net salary loss may receive a fifth-round bonus pick. Remaining spots are filled by draft order."),
          p(strong("Are these picks final? "), "These are projections. Team and conference limits can leave some losses without a pick, and salary ties need draft order to determine the final order. The conference board shows the current projected allocation.")))
    })
  })
}







