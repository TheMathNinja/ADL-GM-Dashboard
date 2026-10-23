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
    current <- if (length(salaries)>1) ceiling(total*100/2-1e-9)/100 else total
    next_year <- round_salary(total-current)
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
