suppressPackageStartupMessages(library(tidyverse))
args<-commandArgs(trailingOnly=TRUE)
if(!length(args))stop('Usage: Rscript scripts/export_performance_scoring_breakdowns.R FFAUC_ROOT [OUTPUT_JSON]')
root<-normalizePath(args[1],mustWork=TRUE)
script<-sub('^--file=','',grep('^--file=',commandArgs(),value=TRUE)[1])
repo_root<-dirname(dirname(normalizePath(script,mustWork=TRUE)))
output<-if(length(args)>1)args[2] else file.path(repo_root,'data/trophy_room/top_performances_reconstructed_breakdowns.json')
source_file<-file.path(root,'HelperFunctions/add_estimated_fafl_pts.R')
# Load function definitions only: no connection setup or source-cache mutations.
for(expr in parse(source_file))if(is.call(expr)&&identical(expr[[1]],as.name('<-'))&&length(expr)==3&&is.call(expr[[3]])&&identical(expr[[3]][[1]],as.name('function')))eval(expr)
code<-c(pass_tds='#P',pass_yd='PY',pass_att='PA',comp='PC',pass_int='IN',sacks_suf='TSK',sack_yd_l='TSY',pass_2pt='P2',rush_tds='#R',rush_yd='RY',rush_att='RA',rush_2pt='R2',rec_tds='#C',rec_yd='CY',rec='CC',tgt='TGT',rec_2pt='C2',off_fum='FUO',off_fum_td='#FR',pen_yd='FY',fd_total='FD',def_fum='FUD',fr_opp='FC',fr_opp_yd='FCY',ff='FF',def_int='IC',def_int_yd='ICY',def_sack='SK',def_sack_yd='SKY',qb_hit='QH',tfl='TKL',safety='SF',def_td='#D',def_2pt_conv='D2',fg_block='BLF',fg_block_td='#BF',punt_block='BLP',punt_block_td='#BP',own_fr='OFC',own_fr_yd='OFCY',pd='PD',tk='TK',as='AS',pat='EP',pat_miss='EM',pat_blk='EM',fg_miss='#M',fg_blk='#M',punt_att='#N',punt_yd='PNY',pt_i20='PI',pt_blk='HBP',st_fum='FUS',pick_six_thrown='#IT',pick_six_thrown_yd='IT',pen='F')
labels<-jsonlite::read_json(file.path(repo_root,'data/trophy_room/mfl-stat-labels.json'),simplifyVector=TRUE)
wanted<-list()
p<-jsonlite::read_json(file.path(repo_root,'docs/trophy-room/top-performances.json'))
h<-jsonlite::read_json(file.path(repo_root,'data/trophy_room/top_performances_history.json'))
for(details in list(p$details,h$details))for(key in names(details)){
 d<-details[[key]]
 if(d$kind=='player'&&d$mode=='current'&&d$year<2026)wanted[[paste(d$year,d$week,sub('.*:','',key),sep=':')]]<-list(year=d$year,week=d$week,id=sub('.*:','',key))
}
out<-list();rules<-get_fafl26_rules()
for(y in 2014:2025){
 target<-Filter(function(d)d$year==y,wanted);if(!length(target))next
 end<-if(y<2021)16 else if(y==2022)18 else 17
 cache<-file.path(root,'caches/add_estimated_fafl_pts',sprintf('nflfastR_calculate_stats_%d_weekly_weeks_1_%d.rds',y,end))
 mapfile<-file.path(root,'caches/gsis_adl_pos_map',sprintf('gsis_adl_pos_map_%d.rds',y))
 d<-readRDS(cache);m<-readRDS(mapfile);d$mfl_id<-as.character(m$mfl_id[match(d$player_id,m$gsis_id)])
 if(y==2022){repl<-d$week==18&d$team %in% c('BUF','CIN');d$week[repl]<-17;d<-d[d$week<=17,];d<-d[!duplicated(paste(d$week,d$mfl_id),fromLast=TRUE),]}
 keys<-paste(y,d$week,d$mfl_id,sep=':');d<-d[keys %in% names(target)&d$season_type=='REG',]
 d$mfl_id<-NULL
 scored<-add_estimated_fafl_pts(d,'ADL26',season=y,map_path=mapfile,keep_details=TRUE)
 for(i in seq_len(nrow(scored))){
  r<-scored[i,];rows<-list()
  for(nm in unique(rules$rule_name)){
   contribution<-r[[paste0('pts_',nm,'_rounded')]]
   if(is.null(contribution)||is.na(contribution)||contribution==0)next
   rule<-rules[rules$rule_name==nm&rules$pos %in% c('ALL',r$score_pos),][1,]
   event_code<-unname(code[nm]);stopifnot(!is.na(event_code))
   label<-labels[[event_code]];if(is.null(label))label<-gsub('_',' ',nm)
   value<-r[[rule$source_col]];if(nm=='sack_yd_l')value<-abs(value)
   # A blocked and a missed kick share an MFL event but remain real separate reconstructed inputs.
   if(nm=='def_td')label<-'Defensive TDs'
   if(nm %in% c('pat_blk','fg_blk'))label<-if(nm=='pat_blk')'Blocked Extra Points' else 'Blocked Field Goals'
   rows[[length(rows)+1]]<-list(eventCode=event_code,event=paste(format(value,trim=TRUE,scientific=FALSE),label),points=as.numeric(contribution))
  }
  if(r$pts_fg!=0)rows[[length(rows)+1]]<-list(eventCode='FG',event='Field goals by distance',points=as.numeric(r$pts_fg))
  total<-sum(vapply(rows,function(row)row$points,numeric(1)))
  stopifnot(abs(total-r$est_fafl_pts)<0.00001)
  out[[paste(y,r$week,r$mfl_id,sep=':')]]<-list(position=r$score_pos,rows=rows,total=as.numeric(total),reconstructed=TRUE,source='Existing ADL26 scoring overlay engine; cached NFL statistics and identical contribution rounding',engineFile=basename(source_file),engineMd5=unname(tools::md5sum(source_file)),statsFile=basename(cache),statsMd5=unname(tools::md5sum(cache)))
 }
 cat(y,nrow(scored),'reconstructed scoring breakdowns\n')
}
jsonlite::write_json(out,output,auto_unbox=TRUE,digits=10,null='null')
