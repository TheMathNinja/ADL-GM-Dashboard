args<-commandArgs(trailingOnly=TRUE)
if(length(args)<2L)stop('Usage: Rscript scripts/export_performance_stat_lines.R FFAUC_ROOT OUTPUT_JSON')
root<-args[1];output<-args[2]
dir.create(dirname(output),recursive=TRUE,showWarnings=FALSE)
labels<-c(completions='Completions',attempts='Pass attempts',passing_yards='Pass yards',passing_tds='Pass TDs',passing_interceptions='Interceptions thrown',sacks_suffered='Sacks taken',carries='Carries',rushing_yards='Rush yards',rushing_tds='Rush TDs',receptions='Receptions',targets='Targets',receiving_yards='Rec yards',receiving_tds='Rec TDs',def_tackles_solo='Solo tackles',def_tackle_assists='Assists',def_tackles_for_loss='Tackles for loss',def_sacks='Sacks',def_qb_hits='QB hits',def_interceptions='Interceptions',def_pass_defended='Passes defended',def_fumbles_forced='Forced fumbles',fumble_recovery_opp='Fumbles recovered',def_tds='Def TDs',fg_made='FG made',fg_missed='FG missed',pat_made='XP made',pat_missed='XP missed',pt_att='Punts',pt_yards='Punt yards',pt_inside_20='Punts inside 20',pt_net_yards='Net punt yards',kickoff_return_yards='Kick return yards',punt_return_yards='Punt return yards',penalties='Penalties',penalty_yards='Penalty yards')
out<-list();sources<-list()
for(y in 2014:2025){
 end<-if(y<2021)16 else if(y==2022)18 else 17
 f<-file.path(root,'caches/add_estimated_fafl_pts',sprintf('nflfastR_calculate_stats_%d_weekly_weeks_1_%d.rds',y,end))
 d<-readRDS(f);mapfile<-file.path(root,'caches/gsis_adl_pos_map',sprintf('gsis_adl_pos_map_%d.rds',y));m<-readRDS(mapfile)
 m<-m[!is.na(m$mfl_id)&nzchar(m$mfl_id),];d$mfl<-m$mfl_id[match(d$player_id,m$gsis_id)];d<-d[!is.na(d$mfl)&d$season_type=='REG',]
 if(y==2022){repl<-d$week==18 & d$team %in% c('BUF','CIN');d$week[repl]<-17;d<-d[d$week<=17,];d<-d[!duplicated(paste(d$week,d$mfl),fromLast=TRUE),]}
 for(i in seq_len(nrow(d))){
  r<-d[i,];values<-lapply(names(labels),function(n){if(!n %in% names(r)||is.na(r[[n]])||r[[n]]==0)return(NULL);as.numeric(r[[n]])});names(values)<-unname(labels);values<-Filter(Negate(is.null),values)
  out[[paste(y,r$week,r$mfl,sep=':')]]<-c(list(team=as.character(r$team),opponent=as.character(r$opponent_team)),values)
 }
 sources[[as.character(y)]]<-list(statsFile=basename(f),statsMd5=unname(tools::md5sum(f)),mapFile=basename(mapfile),mapMd5=unname(tools::md5sum(mapfile)))
 cat(y,'stat lines',nrow(d),'\n')
}
jsonlite::write_json(out,output,auto_unbox=TRUE,null='null',digits=10)
jsonlite::write_json(sources,paste0(output,'.provenance.json'),auto_unbox=TRUE,pretty=TRUE)
