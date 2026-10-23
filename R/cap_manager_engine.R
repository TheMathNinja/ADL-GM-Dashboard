# Monetary values are millions. Match Contract Admin's Sheets rounding.
cap_vet_min <- function(season) {
  values <- c(`2020`=.8, `2021`=.9, `2022`=.9, `2023`=.9, `2024`=1,
              `2025`=1, `2026`=1.1, `2027`=1.1, `2028`=1.2, `2029`=1.2, `2030`=1.3)
  value <- unname(values[as.character(season)])
  if (length(value) != 1L || is.na(value)) stop("Veteran minimum is not configured for this season.")
  value
}

cap_suspended <- function(status) {
  grepl("SUSP", toupper(status)) | toupper(gsub("[() ]", "", status)) == "S"
}

cap_paid <- function(roster) {
  !(toupper(roster$roster_status) %in% c("TAXI", "TAXI_SQUAD") & cap_suspended(roster$injury))
}

cap_spending <- function(roster, adjustment, vet_min) {
  paid <- cap_paid(roster)
  if (anyNA(roster$prev_salary) || anyNA(paid) || !is.finite(adjustment)) stop("Incomplete salary data.")
  vacancy <- max(0, 45 - sum(paid)) * vet_min
  list(paid=sum(paid), empty=max(0, 45-sum(paid)), vacancy=round_salary(vacancy),
       roster=round_salary(sum(roster$prev_salary[paid])), adjustment=adjustment,
       spending=round_salary(sum(roster$prev_salary[paid]) + vacancy + adjustment))
}

cap_projection <- function(finals, franchise_cap, league_cap, forward) {
  if (length(finals) != 17L || any(!is.finite(c(franchise_cap, league_cap, forward)))) stop("Invalid cap inputs.")
  n <- sum(!is.na(finals))
  if (n > 0 && !identical(which(!is.na(finals)), seq_len(n))) stop("Official cap history has a missing week.")
  average <- if (n) round_salary(mean(finals, na.rm=TRUE)) else NA_real_
  projected <- round_salary((sum(finals, na.rm=TRUE) + (17-n)*forward)/17)
  list(weeks=n, remaining=17-n, average=average,
       expected_rollover=if (n) round_salary(min(franchise_cap-average, .1*league_cap)) else NA_real_,
       effective=if (!n) NA_real_ else round_salary((franchise_cap-average)*if (n==17) 1 else 17/(17-n)),
       projected_average=projected, projected_rollover=round_salary(min(franchise_cap-projected, .1*league_cap)))
}

cap_guarantee <- function(row, season) {
  contract <- row$contract[[1]]
  years <- as.numeric(row$prev_years[[1]])
  if (is.na(years) || years <= 0) return("NG")
  if (grepl("\\b1\\.[0-9]{2}\\b|\\b(FT|EFT|NEFT|TT)[0-9]*\\b|\\b5YO\\b|\\+$", contract)) return("FG")
  if (grepl("\\b2\\.[0-9]{2}\\b|EXT", contract, ignore.case=TRUE)) return("SD")
  if (grepl("\\bUDFA\\b|\\b[3-9]\\.[0-9]{2}\\b|^[3-9]\\.XX", contract)) return("NG")
  signed <- suppressWarnings(as.integer(substr(contract, 1, 4)))
  # Guarantee level is fixed at signing, not reclassified after annual raises.
  nfl_caps <- c(`2016`=155.27, `2017`=167, `2018`=177.2, `2019`=188.2,
                `2020`=198.2, `2021`=182.5, `2022`=208.2, `2023`=224.8,
                `2024`=255.4, `2025`=279.2, `2026`=301.2)
  minimum <- unname(nfl_caps[as.character(signed)])
  if (is.na(signed) || is.na(minimum)) return(NA_character_)
  initial <- round_salary(as.numeric(row$prev_salary[[1]]) / 1.1^(season-signed))
  if (initial >= round_salary(minimum/150)) "SD" else "NG"
}

cap_drop_penalty <- function(salary, years, guarantee, status="", as_of=Sys.Date(),
                             claimed=FALSE, accelerate=FALSE, july_tender=FALSE, fifth_year=NA_real_) {
  if (!guarantee %in% c("NG", "SD", "FG") || !is.finite(salary) || !is.finite(years) || years<0 || years!=floor(years)) stop("Invalid drop inputs.")
  if (claimed || guarantee=="NG" || years==0 || grepl("RETIR|DECEASED", toupper(status))) {
    return(list(current=0, next_year=0, total=0))
  }
  relief <- if (cap_suspended(status)) .5 else 1
  if (guarantee=="FG") {
    salaries <- salary * 1.1^(seq_len(years)-1)
    if (is.finite(fifth_year)) salaries <- c(salaries, fifth_year)
    total <- round_salary(sum(salaries)*relief)
    current <- round_salary(salary*relief)
    next_year <- round_salary((sum(salaries)-salary)*relief)
  } else {
    current <- round_salary(.6*salary*relief)
    next_year <- round_salary(.3*salary*max(0,years-1)*relief)
  }
  if ((format(as_of, "%m-%d")<"07-01" && !july_tender) || accelerate) {
    current <- round_salary(current+next_year)
    next_year <- 0
  }
  list(current=current, next_year=next_year, total=round_salary(current+next_year))
}

cap_extension_years <- function(row, week) {
  years <- as.numeric(row$prev_years[[1]])
  eligible <- !grepl("^Ineligible", row$eligibility_note[[1]]) &&
    isTRUE(row$robust_pr_count[[1]] > 0) && is.finite(years) && years<2 && week<=16
  maximum <- if (is.finite(years)) max(0, min(6, floor(6-years))) else 0
  if (eligible && maximum>0) seq_len(maximum) else integer()
}

cap_cash_status <- function(current_net, changes, league_cap) {
  limit <- round_salary(.05*league_cap)
  balance <- round_salary(current_net+sum(changes))
  path <- current_net+cumsum(changes)
  list(net=balance,limit=limit,can_receive=round_salary(limit-balance),
       can_send=round_salary(limit+balance),
       valid=is.finite(current_net) && all(abs(path)<=limit+1e-8))
}

cap_is_cash_adjustment <- function(description) {
  # Some official cash entries say "sends $X ... in a trade" without "cash".
  grepl("\\bcash\\b|\\bsends\\b.*\\$.*\\btrade\\b",description,ignore.case=TRUE)
}

# Peer lines are per-franchise averages; incomplete weeks remain gaps.
cap_history_series <- function(data, franchise, view="expenditures") {
  teams <- data$teams
  i <- match(franchise, teams$franchise)
  stopifnot(!is.na(i), view %in% c("expenditures","space"))
  map <- unique(data$roster[,c("franchise","conference")])
  conference <- map$conference[match(franchise,map$franchise)]
  peers <- which(teams$franchise %in% map$franchise[map$conference==conference])
  values <- as.matrix(data$finals)
  if(view=="space") values <- teams$franchise_cap - values
  groups <- list(Franchise=i, Conference=peers, ADL=seq_len(nrow(teams)))
  result <- lapply(names(groups),function(group) {
    rows <- groups[[group]]
    weekly <- apply(values[rows,,drop=FALSE],2,function(x)
      if(length(x) && all(is.finite(x))) mean(x) else NA_real_)
    cumulative <- vapply(seq_along(weekly),function(w)
      if(all(is.finite(weekly[seq_len(w)]))) mean(weekly[seq_len(w)]) else NA_real_,0.0)
    rbind(data.frame(week=seq_along(weekly),group=group,kind="Weekly",value=weekly),
          data.frame(week=seq_along(weekly),group=group,kind="Cumulative avg.",value=cumulative))
  })
  result <- do.call(rbind,result)
  result$series <- paste(result$group,result$kind,sep=" - ")
  result
}

cap_history_plot <- function(series, selected, franchise_cap, league_cap, view="expenditures") {
  maximum <- .1*league_cap
  limits <- if(view=="space") c(0,maximum) else c(franchise_cap,franchise_cap-maximum)
  labels <- if(view=="space") c("Franchise cap: $0 space",sprintf("Max rollover: $%.2fm space",maximum)) else
    c(sprintf("Franchise salary cap: $%.2fm",limits[1]),sprintf("Max rollover spending level: $%.2fm",limits[2]))
  shown <- series[series$series %in% selected,,drop=FALSE]
  # Separate runs prevent a line bridging a missing official snapshot.
  shown$run <- ave(is.na(shown$value),shown$series,FUN=cumsum)
  ggplot2::ggplot(shown,ggplot2::aes(week,value,color=group,linetype=kind,
      group=interaction(series,run))) +
    ggplot2::annotate("rect",xmin=.8,xmax=17.2,ymin=min(limits),ymax=max(limits),fill="#9ca3af",alpha=.10) +
    ggplot2::geom_hline(yintercept=limits,color="#9ca3af",linetype="dotted") +
    ggplot2::annotate("text",x=17,y=limits,label=labels,hjust=1,vjust=-.6,color="#6b7280",size=3) +
    ggplot2::geom_line(linewidth=.85,na.rm=TRUE) + ggplot2::geom_point(size=1.7,na.rm=TRUE) +
    ggplot2::scale_color_manual(values=c(Franchise="#2563eb",Conference="#b7791f",ADL="#098579")) +
    ggplot2::scale_linetype_manual(values=c(Weekly="solid",`Cumulative avg.`="longdash")) +
    ggplot2::scale_x_continuous(breaks=1:17,limits=c(.8,17.2)) +
    ggplot2::scale_y_continuous(expand=ggplot2::expansion(mult=c(.12,.18))) +
    ggplot2::labs(x="Week",y=if(view=="space") "Cap space ($m)" else "Expenditures ($m)",color=NULL,linetype=NULL) +
    ggplot2::theme_minimal(base_size=12) +
    ggplot2::theme(legend.position="bottom",panel.grid.minor=ggplot2::element_blank())
}


cap_next_outlook <- function(data, franchise, moves=list(), rollover=0) {
  future <- data$next_season
  if(is.null(future)) stop(data$next_season_error %||% "Next-season inputs unavailable; refresh rosters.")
  year <- future$year
  roster <- future$roster[future$roster$franchise==franchise,,drop=FALSE]
  conference <- roster$conference[1]
  roster$origin <- "Current contract"
  for(m in moves) {
    index <- match(m$player_id,roster$player_id)
    if(m$action %in% c("Drop","Trade Away")) {
      if(!is.na(index)) roster <- roster[-index,,drop=FALSE]
    } else if(grepl("^Extend",m$action) && !is.na(index)) {
      roster$prev_salary[index] <- m$contract_salary
      roster$prev_years[index] <- m$contract_years
      roster$contract[index] <- paste(data$season,"EXT scenario")
      roster$next_erfa_eligible[index] <- FALSE
      roster$fifth_year_option_salary[index] <- NA_real_
      roster$origin[index] <- "Scenario extension"
    } else if(m$action=="Trade For") {
      incoming <- future$roster[future$roster$conference==conference &
        future$roster$player_id==m$player_id,,drop=FALSE]
      if(nrow(incoming)!=1) stop("Incoming contract is unavailable in next-season snapshot.")
      incoming$origin <- "Scenario acquisition"
      roster <- dplyr::bind_rows(roster,incoming)
    } else if(m$action=="Sign Player") {
      incoming <- data.frame(player_id=m$player_id,player=m$player,prev_salary=m$contract_salary,
        prev_years=m$contract_years,contract=paste(data$season,"scenario signing"),
        next_erfa_eligible=FALSE,fifth_year_option_salary=NA_real_,origin="Scenario signing")
      roster <- dplyr::bind_rows(roster,incoming)
    }
  }
  if(anyNA(roster$prev_years) || anyNA(roster$prev_salary)) stop("Missing contract years or salaries.")
  roster$next_years <- pmax(0,roster$prev_years-1)
  roster$next_salary <- round_salary(roster$prev_salary*1.1)
  roster$next_status <- ifelse(roster$next_years>0,roster$origin,"Expires; not retained")
  erfa <- roster$prev_years==1 & !is.na(roster$next_erfa_eligible) & roster$next_erfa_eligible
  option <- roster$prev_years==1 & grepl("\\+$",roster$contract) &
    is.finite(roster$fifth_year_option_salary)
  if(any(roster$prev_years==1 & grepl("\\+$",roster$contract) & !is.finite(roster$fifth_year_option_salary)))
    stop("An exercised fifth-year option salary is unavailable.")
  roster$next_years[erfa | option] <- 1
  roster$next_status[erfa] <- "ERFA tag assumed"
  roster$next_status[option] <- "Exercised fifth-year option"
  roster$next_salary[option] <- roster$fifth_year_option_salary[option]
  roster$next_salary[roster$next_years==0] <- 0
  picks <- future$picks[future$picks$franchise==franchise,,drop=FALSE]
  growth <- future$rules$rookieGrowth
  wages <- growth$pools$wages[[which(growth$pools$year==growth$baseYear)]]
  if(nrow(picks)) {
    picks$overall <- (picks$round-1)*16+picks$slot
    picks$salary <- vapply(picks$overall,function(p) {
      lo <- floor(p); hi <- ceiling(p)
      round_salary((wages[lo]*(hi-p)+wages[hi]*(p-lo)+if(lo==hi) wages[lo] else 0)*
        growth$annualMultiplier^(year-growth$baseYear))
    },0.0)
    rookies <- data.frame(player_id=paste0("pick:",seq_len(nrow(picks))),
      player=paste0("R",picks$round," ",picks$original," pick (projected ",picks$slot,")"),
      next_years=4,next_salary=picks$salary,next_status="Draft rookie assumed signed",origin="Draft reserve")
    roster <- dplyr::bind_rows(roster,rookies)
  }
  retained <- roster$next_years>0
  empty <- max(0,45-sum(retained))
  salaries <- round_salary(sum(roster$next_salary))
  vacancy <- round_salary(empty*cap_vet_min(year))
  official <- future$adjustments$adjustment[match(franchise,future$adjustments$franchise)]
  added <- round_salary(sum(vapply(moves,function(m)m$next_year,0.0)))
  cap <- future$rules$capGrowth
  league <- round_salary(cap$intercept+cap$slope*(year-cap$origin))
  franchise_cap <- round_salary(league+rollover)
  spending <- round_salary(salaries+vacancy+official+added)
  list(year=year,league_cap=league,franchise_cap=franchise_cap,rollover=rollover,
    salaries=salaries,vacancy=vacancy,official_adjustments=round_salary(official),
    scenario_penalties=added,spending=spending,space=round_salary(franchise_cap-spending),
    empty=empty,paid=sum(retained),erfas=sum(erfa),picks=picks,roster=roster)
}


cap_time_et <- function(value, pattern="%Y-%m-%d %H:%M:%S") {
  stamp <- as.POSIXct(value,format="%Y-%m-%d %H:%M:%S",tz="UTC")
  if(length(stamp)!=1 || is.na(stamp)) return("Unavailable")
  paste(format(stamp,pattern,tz="America/New_York"),"ET")
}

cap_team_brand <- function(players, code) {
  # Visuals belong to the NFL player team, not that player's ADL owner.
  names <- unique(players[,c("franchise","franchise_name")])
  index <- match(code,names$franchise)
  if(is.na(index) && code %in% c("JAX","JAC")) index <- match(if(code=="JAX") "JAC" else "JAX",names$franchise)
  name <- names$franchise_name[index]
  if(length(name)!=1 || is.na(name) || !nzchar(name)) name <- code
  nfl_code <- if(code %in% c("JAX","JAC")) "JAC" else code
  visuals <- players[players$player_team==nfl_code & !is.na(players$player_team),,drop=FALSE]
  color <- function(field,fallback) {
    x <- visuals[[field]]
    x <- x[!is.na(x) & grepl("^#[0-9a-fA-F]{6}$",x)]
    if(length(x)) x[1] else fallback
  }
  primary <- color("team_color","#203d5c")
  secondary <- color("team_color2","#c83a3f")
  rgb <- as.numeric(grDevices::col2rgb(primary))/255
  linear <- ifelse(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)^2.4)
  luminance <- sum(linear*c(.2126,.7152,.0722))
  text <- if((luminance+.05)/.05 >= 1.05/(luminance+.05)) "#000000" else "#FFFFFF"
  logo <- visuals$team_logo_espn
  logo <- logo[!is.na(logo) & grepl("^https://",logo)]
  list(name=name,primary=primary,secondary=secondary,text=text,logo=if(length(logo)) logo[1] else NA_character_)
}
