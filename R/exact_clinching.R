# A label is a mathematical certificate, never unanimity in Monte Carlo draws.
adl_exact_clinching <- function(standings, history, schedule, season, week,
                               max_week=12L, root=getwd()) {
  scratch <- tempfile('exact-clinch-');dir.create(scratch)
  on.exit(unlink(scratch,recursive=TRUE),add=TRUE)
  teams <- standings[,c('franchise_id','conference','division','total_wins')]
  teams$franchise_id <- as.character(teams$franchise_id)
  teams$wins2 <- round(2*teams$total_wins)
  if (any(abs(teams$wins2-2*teams$total_wins)>1e-7)) stop('Invalid adjusted wins for clinch proof.')
  teams$total_wins <- NULL
  observations <- history[history$season==season & history$week<=week,
                          c('week','franchise_id','points_for_week','potential_points_week')]
  games <- unique(schedule[schedule$week<=max_week,
                           c('week','franchise_id','opponent_id')])
  request <- list(season=season,week=week,max_week=max_week,teams=teams,
                  observations=observations,schedule=games)
  input <- file.path(scratch,'input.json');output <- file.path(scratch,'output.json')
  jsonlite::write_json(request,input,auto_unbox=TRUE,dataframe='rows',digits=NA,na='null')
  python <- Sys.getenv('BONUS_PYTHON',Sys.which('python3'))
  if (!nzchar(python)) python <- Sys.which('python')
  if (!nzchar(python)) stop('Python with z3-solver is required for mathematical clinching.')
  python_root <- Sys.getenv('Python_ROOT_DIR',Sys.getenv('pythonLocation'))
  child_env <- character()
  if (.Platform$OS.type!='windows' && nzchar(python_root)) {
    child_env <- c(paste0('PYTHONHOME=',shQuote(python_root)),
                   paste0('LD_LIBRARY_PATH=',shQuote(file.path(python_root,'lib'))))
  }
  args <- c(shQuote(file.path(root,'scripts','exact_clinching.py')),
            '--input',shQuote(input),'--output',shQuote(output),
            '--cache-dir',shQuote(file.path(root,'data','clinching',as.character(season))))
  status <- system2(python,args,env=child_env)
  if (!identical(as.integer(status),0L)) stop('Mathematical clinch check failed; refusing simulation-based labels.')
  proof <- jsonlite::fromJSON(output,simplifyVector=FALSE)
  flags <- proof$teams
  if (!setequal(names(flags),teams$franchise_id)) stop('Clinch proof identities do not match standings.')
  ix <- lapply(as.character(standings$franchise_id),function(id) flags[[id]])
  standings$clinch_bye <- vapply(ix,function(x)isTRUE(x$bye),logical(1))
  standings$clinch_division <- vapply(ix,function(x)isTRUE(x$division),logical(1))
  standings$clinch_playoffs <- vapply(ix,function(x)isTRUE(x$playoffs),logical(1))
  standings$eliminated_playoffs <- vapply(ix,function(x)isTRUE(x$eliminated),logical(1))
  standings$eliminated_division <- vapply(ix,function(x)isTRUE(x$eliminated_division),logical(1))
  standings$eliminated_bye <- vapply(ix,function(x)isTRUE(x$eliminated_bye),logical(1))
  standings$clinch <- vapply(ix,function(x)x$clinch,character(1))
  standings
}
