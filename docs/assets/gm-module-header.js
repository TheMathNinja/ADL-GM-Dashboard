/* Shared Bonus Games masthead for the ADL and FAFL GM modules. */
(()=>{
  const header=document.currentScript?.previousElementSibling;
  if(!header?.matches('header[data-gm-module-header]'))return;

  const {league,logo,season,seasonId}=header.dataset;
  const title=header.querySelector('h1');
  const image=document.createElement('img');
  image.className='gm-shield';
  image.src=logo;
  image.alt=league+' logo';

  const identity=document.createElement('div');
  const overline=document.createElement('div');
  overline.className='gm-overline';
  const label=document.createElement('span');
  if(seasonId)label.id=seasonId;
  label.textContent=season;
  overline.append(league+' GM Dashboard ',label);
  identity.append(overline,title);

  const menu=document.createElement('details');
  menu.className='gm-dashboard-menu';
  menu.setAttribute('data-gm-menu','');
  menu.innerHTML='<summary aria-label="Open dashboard menu" title="Open dashboard menu"><span class="gm-menu-icon" aria-hidden="true"></span></summary><nav aria-label="GM dashboard tools"><a class="gm-overview-link" href="../"><span class="gm-overview-icon" aria-hidden="true">&#8610;</span><span class="gm-overview-copy"><strong>GM Dashboard</strong><small>Back to all GM modules</small></span></a></nav>';

  header.append(image,identity,menu);
})();
