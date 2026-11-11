/* Only optional filler islands follow climate weights. Mandatory cultures,
 * all six climates and the existing essential-resource prelude run first. */
static uint32_t wsClimateWeight(const WSWorldSettings*s,uint32_t climate){
 static const uint8_t weights[4][6]={
  {1,1,1,1,1,1}, /* Balanced. */
  {1,1,4,4,1,1}, /* Temperate: northern and prairie. */
  {1,1,1,1,4,4}, /* Tropical: jungle and steppe. */
  {4,4,1,1,1,1}  /* Polar: polar and tundra. */
 };
 return s->climateBalance>=0&&s->climateBalance<=3&&climate<6?
  weights[s->climateBalance][climate]:0;
}
static int wsChooseBalancedFill(const WSWorldSettings*s,uint32_t count){
 if(count>=WS_LIMIT||s->climateBalance<0||s->climateBalance>3)return -1;
 uint32_t climates[6]={0},available[6]={0},choices[6],choiceCount=0,best=0;
 for(uint32_t i=0;i<count;i++){
  if(planned[i].climate>=6)return -1;
  climates[planned[i].climate]++;
 }
 for(uint32_t i=0;i<WS_COUNT;i++)
  if(wsSelectionMatch(i,s,0,-1,0,0,1,0)&&wsClimateQuotaFiller(s,wsTemplates[i].climate))available[wsTemplates[i].climate]=1;
 for(uint32_t c=0;c<6;c++)if(available[c]){
  uint32_t weight=wsClimateWeight(s,c);
  if(!weight)return -1;
  /* Compare ratios exactly; flooring would overfill low-weight climates. */
  uint32_t left=climates[c]*wsClimateWeight(s,best),right=climates[best]*weight;
  if(!choiceCount||left<right){best=c;choiceCount=0;}
  if(!choiceCount||climates[c]*wsClimateWeight(s,best)==climates[best]*weight)
   choices[choiceCount++]=c;
 }
 if(!choiceCount)return -1;
 return wsChoose(s,0,(int)choices[wsRandom()%choiceCount],0,0,1,0);
}
