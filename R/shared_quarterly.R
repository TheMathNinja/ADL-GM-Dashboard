# Python supplies paired normal playoff scores and selected-model quarter outcomes.
# Both consumers call the same implementation; no R copy of the Bonus model.
adl_shared_quarterly <- function(history, team_ids, season, week, n_sims,
                                 mu, weekly_sd, strength_sd, root = getwd()) {
  scratch <- tempfile('quarterly-bonus-');dir.create(scratch)
  on.exit(unlink(scratch, recursive=TRUE), add=TRUE)
  current <- history[history$season==season & history$week<=week,
                     c('season','week','franchise_id','points_for_week','potential_points_week')]
  write.csv(current,file.path(scratch,'current.csv'),row.names=FALSE)
  jsonlite::write_json(list(ids=as.character(team_ids),mu=as.numeric(mu),
                           sigma=as.numeric(weekly_sd),tau=as.numeric(strength_sd)),
                      file.path(scratch,'primary.json'),auto_unbox=TRUE,digits=NA)
  python <- Sys.getenv('BONUS_PYTHON',Sys.which('python3'))
  if (!nzchar(python)) python <- Sys.which('python')
  if (!nzchar(python)) stop('Python with numpy/pandas is required for the shared quarterly model.')
  args <- c(shQuote(file.path(root,'scripts','quarterly_bonus.py')),
            '--root',shQuote(root),'--current',shQuote(file.path(scratch,'current.csv')),
            '--primary',shQuote(file.path(scratch,'primary.json')),
            '--out',shQuote(scratch),'--season',season,'--week',week,'--simulations',n_sims)
  # R changes Linux's loader path. Pin Python's own runtime/library root so
  # its subprocess does not resolve Ubuntu's system Python site-packages.
  python_root <- Sys.getenv('Python_ROOT_DIR', Sys.getenv('pythonLocation'))
  child_env <- character()
  if (.Platform$OS.type != 'windows' && nzchar(python_root)) {
    child_env <- c(paste0('PYTHONHOME=',shQuote(python_root)),
                   paste0('LD_LIBRARY_PATH=',shQuote(file.path(python_root,'lib'))))
  }
  status <- system2(python,args,env=child_env)
  if (!identical(as.integer(status),0L)) stop('Shared quarterly model failed; refusing a divergent playoff forecast.')
  read_array <- function(name,dims) {
    path <- file.path(scratch,name);size <- prod(dims)
    if (file.info(path)$size != size*8) stop('Invalid shared quarterly simulation size.')
    array(readBin(path,'double',n=size,size=8,endian='little'),dim=dims)
  }
  list(native=read_array('native.bin',c(length(team_ids),12L-week,n_sims)),
       quarters=read_array('quarters.bin',c(length(team_ids),4L,n_sims)),
       metadata=jsonlite::fromJSON(file.path(scratch,'metadata.json')))
}
