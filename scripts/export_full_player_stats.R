suppressPackageStartupMessages(library(tidyverse))
args<-commandArgs(trailingOnly=TRUE);root<-normalizePath(args[1],mustWork=TRUE);workspace<-normalizePath(args[2],mustWork=TRUE)
source_file<-file.path(root,'HelperFunctions/add_estimated_fafl_pts.R')
for(expr in parse(source_file))if(is.call(expr)&&identical(expr[[1]],as.name('<-'))&&length(expr)==3&&is.call(expr[[3]])&&identical(expr[[3]][[1]],as.name('function')))eval(expr)
wanted<-jsonlite::read_json(file.path(workspace,'wanted-games.json'));wanted_keys<-unique(unlist(lapply(wanted,names)));rules<-get_fafl26_rules();labels<-jsonlite::read_json(file.path(workspace,'ADL/data/trophy_room/mfl-stat-labels.json'),simplifyVector=TRUE)
code<-c(pass_tds='#P',pass_yd='PY',pass_att='PA',comp='PC',pass_int='IN',sacks_suf='TSK',sack_yd_l='TSY',pass_2pt='P2',rush_tds='#R',rush_yd='RY',rush_att='RA',rush_2pt='R2',rec_tds='#C',rec_yd='CY',rec='CC',tgt='TGT',rec_2pt='C2',off_fum='FUO',off_fum_td='#FR',pen_yd='FY',fd_total='FD',def_fum='FUD',fr_opp='FC',fr_opp_yd='FCY',ff='FF',def_int='IC',def_int_yd='ICY',def_sack='SK',def_sack_yd='SKY',qb_hit='QH',tfl='TKL',safety='SF',def_td='#D',def_2pt_conv='D2',fg_block='BLF',fg_block_td='#BF',punt_block='BLP',punt_block_td='#BP',own_fr='OFC',own_fr_yd='OFCY',pd='PD',tk='TK',as='AS',pat='EP',pat_miss='EM',pat_blk='EM',fg_miss='#M',fg_blk='#M',punt_att='#N',punt_yd='PNY',pt_i20='PI',pt_blk='HBP',st_fum='FUS',pick_six_thrown='#IT',pick_six_thrown_yd='IT',pen='F')
pref<-list(QB=c('PC','PA','PY','#P','P2','IN','TSK','TSY','RA','RY','#R','R2','FD','FUO','FL','FUS','OFC','OFCY','#FR','FR','F','FY'),skill=c('RA','RY','#R','R2','CC','TGT','CY','#C','C2','FD','FUO','FL','FUS','FUD','OFC','OFCY','#FR','FR','FC','FCY','#DR','TK','AS','TKL','F','FY'),defense=c('TK','AS','TKL','QH','SK','SKY','PD','FF','FC','FCY','#DR','IC','ICY','#IR','F','FY'))
extra<-c(PC='completions',PA='attempts',PY='passing_yards','#P'='passing_tds',P2='passing_2pt_conversions',IN='passing_interceptions',TSK='sacks_suffered',TSY='sack_yards_lost',RA='carries',RY='rushing_yards','#R'='rushing_tds',R2='rushing_2pt_conversions',CC='receptions',TGT='targets',CY='receiving_yards','#C'='receiving_tds',C2='receiving_2pt_conversions',FD='first_downs_total',FUO='offensive_fumbles',FL='fumbles_lost_total',FUD='defensive_fumbles',FUS='special_teams_fumbles',OFC='fumble_recovery_own',OFCY='fumble_recovery_yards_own','#FR'='offensive_fumble_recovery_tds',TK='mfl_tackles',AS='def_tackle_assists',TKL='def_tackles_for_loss',QH='def_qb_hits',SK='def_sacks',SKY='def_sack_yards',PD='def_pass_defended',FF='def_fumbles_forced',FC='fumble_recovery_opp',FCY='fumble_recovery_yards_opp','#D'='def_tds',IC='def_interceptions',ICY='def_interception_yards',F='penalties',FY='penalty_yards',SF='def_safeties',D2='my_def_2pt_conv',BLF='my_fg_block','#BF'='my_fg_block_td',BLP='my_punt_block','#BP'='my_punt_block_td',EP='pat_made','#N'='pt_att',PNY='pt_yards',PI='pt_inside_20',HBP='pt_blocked',KY='kickoff_return_yards',UY='punt_return_yards','#K'='kickoff_returns','#U'='punt_returns')
outdir<-file.path(workspace,'nfl-games');dir.create(outdir,showWarnings=FALSE);provenance<-if(file.exists(file.path(outdir,'provenance.json')))jsonlite::read_json(file.path(outdir,'provenance.json')) else list()
for(y in 2014:2025){
 end<-if(y<2021)16 else if(y==2022)18 else 17;f<-file.path(root,'caches/add_estimated_fafl_pts',sprintf('nflfastR_calculate_stats_%d_weekly_weeks_1_%d.rds',y,end));mapfile<-file.path(root,'caches/gsis_adl_pos_map',sprintf('gsis_adl_pos_map_%d.rds',y));d<-readRDS(f);m<-readRDS(mapfile);d$mfl_id<-as.character(m$mfl_id[match(d$player_id,m$gsis_id)])
 if(y==2022){repl<-d$week==18&d$team %in% c('BUF','CIN');d$week[repl]<-17;d<-d[d$week<=17,];d<-d[!duplicated(paste(d$week,d$mfl_id,d$season_type),fromLast=TRUE),]}
 existing_path<-file.path(outdir,paste0(y,'.json'));out<-if(file.exists(existing_path))jsonlite::read_json(existing_path) else list();needed_keys<-setdiff(wanted_keys,names(out));keys<-paste(y,d$week,d$mfl_id,sep=':');d<-d[keys %in% needed_keys & d$season_type=='REG',];if(!nrow(d))next;ids<-d$mfl_id;d$mfl_id<-NULL
 scored<-add_estimated_fafl_pts(d,'ADL26',season=y,map_path=mapfile,keep_details=TRUE)
 for(i in seq_len(nrow(scored))){
  r<-scored[i,];events<-list()
  for(ev in names(extra)){nm<-extra[[ev]];if(nm %in% names(r)&&!is.na(r[[nm]])){value<-as.numeric(r[[nm]]);if(ev=='TSY')value<-abs(value);events[[ev]]<-value}}
  for(pair in list(c('EM','pat_missed','pat_blocked'),c('#M','fg_missed','fg_blocked'))){v<-sum(vapply(pair[-1],function(nm)if(nm %in% names(r)&&!is.na(r[[nm]]))as.numeric(r[[nm]])else 0,numeric(1)));events[[pair[1]]]<-v}
  distances<-as.numeric(unlist(strsplit(as.character(r$fg_made_list %||% ''),'[;,]')));distances<-distances[is.finite(distances)];if(length(distances))events$FG<-as.list(distances)
  rows<-list();selected<-if(r$score_pos=='QB')pref$QB else if(r$score_pos %in% c('RB','WR','TE'))pref$skill else if(r$score_pos %in% c('DT','DE','LB','CB','S'))pref$defense else names(extra)
  for(nm in unique(rules$rule_name)){
   rule<-rules[rules$rule_name==nm&rules$pos %in% c('ALL',r$score_pos),];if(!nrow(rule))next;rule<-rule[1,];contribution<-r[[paste0('pts_',nm,'_rounded')]];if(is.null(contribution)||is.na(contribution))next
   event_code<-unname(code[nm]);stopifnot(!is.na(event_code));if(contribution==0&&!event_code %in% selected)next
   label<-labels[[event_code]];if(is.null(label))label<-gsub('_',' ',nm);if(nm=='def_td')label<-'Defensive TDs';if(nm %in% c('pat_blk','fg_blk'))label<-if(nm=='pat_blk')'Blocked Extra Points' else 'Blocked Field Goals'
   value<-as.numeric(r[[rule$source_col]]);if(nm=='sack_yd_l')value<-abs(value)
   rows[[length(rows)+1]]<-list(eventCode=event_code,category=nm,value=value,label=label,event=paste(format(value,trim=TRUE,scientific=FALSE),label),points=as.numeric(contribution))
  }
  if(length(distances))for(distance in distances)rows[[length(rows)+1]]<-list(eventCode='FG',category='fg',value=distance,label='Field Goal Distance',event=paste(distance,'Field Goal Distance'),points=score_fg_made_distances_rounded(distance))
  if(!length(distances)&&r$score_pos %in% c('PK','PN'))rows[[length(rows)+1]]<-list(eventCode='FG',category='fg',value=0,label='Field Goals Made',event='0 Field Goals Made',points=0)
  total<-sum(vapply(rows,function(row)row$points,numeric(1)));stopifnot(abs(total-r$est_fafl_pts)<.00001)
  out[[paste(y,r$week,ids[i],sep=':')]]<-list(position=r$score_pos,team=r$team,opponent=r$opponent_team,events=events,current=list(rows=rows,total=total,reconstructed=TRUE,source='Audited ADL26 engine with cached nflfastR statistics; identical per-category rounding'))
 }
 jsonlite::write_json(out,file.path(outdir,paste0(y,'.json')),auto_unbox=TRUE,digits=10,null='null');provenance[[as.character(y)]]<-list(statsFile=basename(f),statsMd5=unname(tools::md5sum(f)),mapFile=basename(mapfile),mapMd5=unname(tools::md5sum(mapfile)),engineMd5=unname(tools::md5sum(source_file)));cat(y,length(out),'full NFL game stat lines exported\n')
}
jsonlite::write_json(provenance,file.path(outdir,'provenance.json'),auto_unbox=TRUE,pretty=TRUE)
ownership<-list();roster_sources<-list()
for(lg in names(wanted)){
 own<-list();source_list<-list()
 for(y in sort(unique(vapply(wanted[[lg]],function(d)d$year,numeric(1))))){
  f<-file.path(root,'RawLeagueData',sprintf('ff_rosters_%s%02d_%d_raw.rds',lg,y%%100,y));r<-readRDS(f);if(!'week'%in%names(r)){candidate<-sub('_raw.rds$','_raw_weekly_candidate.rds',f);stopifnot(file.exists(candidate));f<-candidate;r<-readRDS(f)};stopifnot('week'%in%names(r));keys<-paste(y,r$week,as.character(r$player_id),sep=':');r<-r[keys %in% names(wanted[[lg]]),c('week','player_id','franchise_id')];r<-unique(r)
  for(key in unique(paste(y,r$week,r$player_id,sep=':'))){parts<-strsplit(key,':',fixed=TRUE)[[1]];own[[key]]<-as.list(unique(as.character(r$franchise_id[r$week==as.integer(parts[2])&r$player_id==parts[3]])))}
  source_list[[as.character(y)]]<-list(file=basename(f),md5=unname(tools::md5sum(f)))
 }
 ownership[[lg]]<-own;roster_sources[[lg]]<-source_list;cat(lg,length(own),'weekly roster ownership entries exported\n')
}
jsonlite::write_json(list(ownership=ownership,sources=roster_sources),file.path(workspace,'weekly-ownership.json'),auto_unbox=TRUE)
