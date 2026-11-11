/* Keep native size/rank restrictions and quota filters authoritative. Variety
 * is a preference among the remaining candidates, never a reason to silently
 * remove a climate, culture, special faction or essential resource. */
static int wsChoose(const WSWorldSettings*s,uint32_t requiredCulture,int climate,int ore,int whale,int empty,int faction){
 int first=wsChooseOriginal(s,requiredCulture,climate,ore,whale,empty,faction);
 if(first<0||s->islandVariety==0||wsVarietyRelaxed)return first;
 uint32_t best=UINT32_MAX,choice=0,count=0;
 for(uint32_t i=0;i<WS_COUNT;i++){
  if(!wsSelectionMatch(i,s,requiredCulture,climate,ore,whale,empty,faction))continue;
  if(s->islandSize==4&&(wsSelectionSmallest?wsTemplates[i].width!=wsTemplates[first].width:wsSelectionRanks[i]!=wsSelectionRanks[first]))continue;
  uint32_t score=wsIslandVarietyScore(s,i);
  if(score<best){best=score;count=0;}
  if(score==best&&(++count==1u||wsRandom()%count==0))choice=i;
 }
 return count?(int)choice:-1;
}
