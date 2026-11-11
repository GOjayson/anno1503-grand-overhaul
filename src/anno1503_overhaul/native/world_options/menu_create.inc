/* Six pages keep the existing and advanced choices readable while the map
 * preview, seed, status and Start controls remain visible. */
static int wsCreateMenu(DialogState*d,HWND w){
 const char*diff[]={"Easy","Medium","Hard"};
 const char*size[]={"Small (smallest available)","Medium (128 tiles)","Big (strict)","Mixed","Big (lenient)"};
 const char*worlds[]={"Small (256 x 256)","Medium (512 x 512)","Big (1024 x 1024)","Huge (2048 x 2048) - experimental"};
 const char*ai[]={"0","1","2","3"};
 const char*money[]={"10,000","30,000","50,000","80,000","100,000"};
 const char*fleet[]={"Single ship (small trade ship)","War fleet (3 armed ships)","Merchant fleet (3 trade ships)"};
 const char*aggression[]={"Peaceful","Easy","Medium","Hard"};
 const char*fertility[]={"Very fertile","Medium fertility","Low fertility","Mixed"};
 const char*balance[]={"Balanced","Favour temperate","Favour tropical","Favour polar"};
 const char*layout[]={"Evenly spread","Grouped archipelagos","Central ocean"};
 const char*climate[]={"Any climate","Polar","Tundra","North","Prairie","Jungle","Steppe"};
 const char*distribution[]={"Original distribution","Spread resources","Specialised regions"};
 const char*separation[]={"Close neighbours","Balanced separation","Distant rivals"};
 const char*visibility[]={"Unexplored (terra incognita)","Geography revealed","Fully explored"};
 const char*enemies[]={"Strict line of sight","Reveal all activity"};
 const char*activity[]={"Rare","Normal","Frequent"};
 const char*strength[]={"Weak","Normal","Strong"};
 const char*tabs[]={"World","Players","Starting","Presets","Islands","Visibility"};
 d->creatingPage=-1;d->preferredIsland=d->inspectedIsland=-1;d->pageControlCount=0;
 label(d,"World Settings",24,18,632,28);
 for(int i=0;i<6;i++)control(d,"BUTTON",tabs[i],BS_PUSHBUTTON|WS_TABSTOP,24+i*106,58,102,32,ID_TAB_WORLD+i);

 d->creatingPage=0;
 label(d,"World generation",24,108,632,24);
 label(d,"World size",24,142,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,164,296,180,ID_WORLD_SIZE),worlds,4,2);
 label(d,"Island count",348,142,296,20);control(d,"EDIT","24",WS_BORDER|ES_NUMBER|WS_TABSTOP,348,164,296,27,ID_COUNT);
 label(d,"Island size",24,204,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,226,296,180,ID_SIZE),size,5,3);
 label(d,"Minimum spacing (tiles)",348,204,296,20);control(d,"EDIT","16",WS_BORDER|ES_NUMBER|WS_TABSTOP,348,226,296,27,ID_SPACING);
 label(d,"Plant fertility",24,266,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,288,296,180,ID_PLANT_FERTILITY),fertility,4,1);
 label(d,"Mineral fertility",348,266,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,348,288,296,180,ID_MINERAL_FERTILITY),fertility,4,1);
 label(d,"Climate balance",24,328,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,350,296,180,ID_CLIMATE_BALANCE),balance,4,0);
 label(d,"Layout style",348,328,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,348,350,296,180,ID_LAYOUT_STYLE),layout,3,0);
 label(d,"Resource distribution",24,396,620,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,418,620,180,ID_RESOURCE_DISTRIBUTION),distribution,3,0);
 control(d,"BUTTON","Guarantee basic resources near every player's start",BS_AUTOCHECKBOX|WS_TABSTOP,24,464,620,28,ID_GUARANTEE_BASICS);
 label(d,"Spread separates each resource; Specialised regions groups it. Fertility controls world abundance; individual islands can differ.\r\n\r\nNearby basics: grain, flax, potatoes, iron and salt within a quarter world (at least 128 tiles) of each starting island's edge. May add resources above fertility; not the complete Food diet.",24,510,620,138);

 d->creatingPage=1;
 label(d,"Players and cultures",24,108,632,24);
 label(d,"Stock difficulty preset",24,142,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,164,296,180,ID_DIFFICULTY),diff,3,1);
 label(d,"AI opponents",348,142,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP,348,164,296,100,ID_AI),ai,4,0);
 label(d,"AI difficulty",24,204,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,226,296,180,ID_AI_DIFFICULTY),aggression,4,1);
 label(d,"Peaceful AI never starts a war. Other levels increase its chance of starting one.",348,212,296,54);
 label(d,"Native cultures",24,284,632,22);
 for(int i=0;i<8;i++){HWND c=control(d,"BUTTON",cultureNames[i],BS_AUTOCHECKBOX|WS_TABSTOP,24+(i%2)*324,314+(i/2)*32,296,26,ID_CULTURE+i);SendMessageA(c,BM_SETCHECK,BST_CHECKED,0);}
 label(d,"Pirates and Venetians",24,470,632,22);
 const char*special[]={"Pirates","Venetians"};for(int i=0;i<2;i++){HWND c=control(d,"BUTTON",special[i],BS_AUTOCHECKBOX|WS_TABSTOP,24+i*324,500,296,26,ID_FACTION+i);SendMessageA(c,BM_SETCHECK,BST_CHECKED,0);}
 label(d,"Pirate reinforcement frequency",24,540,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,562,296,140,ID_PIRATE_FREQUENCY),activity,3,1);
 label(d,"Pirate strength (new ships)",348,540,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,348,562,296,140,ID_PIRATE_STRENGTH),strength,3,1);
 label(d,"Neutral merchant trade frequency",24,602,620,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,624,620,140,ID_MERCHANT_FREQUENCY),activity,3,1);
 label(d,"Routes and fleet limits still affect raid and merchant arrival times.",24,650,620,18);

 d->creatingPage=2;
 label(d,"Starting options",24,108,632,24);
 label(d,"Starting money",24,142,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,164,296,180,ID_MONEY),money,5,1);
 label(d,"Starting fleet",348,142,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,348,164,296,180,ID_FLEET),fleet,3,0);
 label(d,"Preferred starting climate",24,204,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,226,296,220,ID_START_CLIMATE),climate,7,0);
 control(d,"BUTTON","Use automatic starting position",BS_PUSHBUTTON|WS_TABSTOP,348,224,296,30,ID_CLEAR_START);
 control(d,"BUTTON","Balance starting islands for human and AI players",BS_AUTOCHECKBOX|WS_TABSTOP,24,272,620,28,ID_FAIR_STARTS);
 label(d,"Player separation",24,312,296,20);fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,334,296,180,ID_START_SEPARATION),separation,3,1);
 label(d,"Uses comparable fertile land and resource access. Inspect islands and the start summary on the Islands page.",348,310,296,62);
 control(d,"BUTTON","Custom cargo on every trade ship",BS_AUTOCHECKBOX|WS_TABSTOP,24,388,620,28,ID_CARGO_MODE);
 label(d,"Tools (tons)",24,430,188,20);control(d,"EDIT","40",WS_BORDER|ES_NUMBER|WS_TABSTOP,24,452,188,27,ID_CARGO_TOOLS);
 label(d,"Wood (tons)",240,430,188,20);control(d,"EDIT","40",WS_BORDER|ES_NUMBER|WS_TABSTOP,240,452,188,27,ID_CARGO_WOOD);
 label(d,"Food (tons)",456,430,188,20);control(d,"EDIT","10",WS_BORDER|ES_NUMBER|WS_TABSTOP,456,452,188,27,ID_CARGO_FOOD);
 label(d,"Each good uses separate 50-ton holds. Small trade ships have 4 holds; big trade ships have 8. Cargo must fit every trade ship. Leave unchecked for standard supplies. Warship cannons are retained.",24,502,620,74);
 HWND disasters=control(d,"BUTTON","Enable disasters",BS_AUTOCHECKBOX|WS_TABSTOP,24,592,620,28,ID_DISASTERS);SendMessageA(disasters,BM_SETCHECK,BST_CHECKED,0);

 d->creatingPage=3;
 label(d,"Saved world presets",24,108,632,24);
 label(d,"Preset name (letters, numbers, spaces, _ or -)",24,150,620,22);
 control(d,"EDIT","My world",WS_BORDER|WS_TABSTOP,24,176,620,28,ID_PRESET_NAME);SendDlgItemMessageA(w,ID_PRESET_NAME,EM_SETLIMITTEXT,WS_PRESET_NAME_MAX,0);
 label(d,"Saved presets",24,226,620,22);control(d,"COMBOBOX","",CBS_DROPDOWNLIST|CBS_SORT|WS_TABSTOP|WS_VSCROLL,24,252,620,220,ID_PRESET_PICK);
 control(d,"BUTTON","Save current settings",BS_PUSHBUTTON|WS_TABSTOP,24,312,296,34,ID_PRESET_SAVE);
 control(d,"BUTTON","Load selected preset",BS_PUSHBUTTON|WS_TABSTOP,348,312,296,34,ID_PRESET_LOAD);
 label(d,"Presets keep the seed and every option, including a preferred starting island. Load a preset to recreate its preview.\r\n\r\nThe same seed and the same world settings reproduce the map preview in this generator version. A seed alone does not include your other choices.\r\n\r\nPresets stay with this modded game copy and are kept when restoring original game files.",24,394,620,190);

 d->creatingPage=4;
 label(d,"Island details and starting conditions",24,108,632,24);
 control(d,"BUTTON","Use inspected island as preferred starting position",BS_PUSHBUTTON|WS_TABSTOP,24,146,620,34,ID_USE_ISLAND);
 control(d,"EDIT","",WS_BORDER|ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL|WS_TABSTOP,24,196,620,326,ID_ISLAND_DETAILS);
 label(d,"Starting-position and resource summary",24,540,620,22);
 control(d,"EDIT","",WS_BORDER|ES_MULTILINE|ES_READONLY|ES_AUTOVSCROLL|WS_VSCROLL|WS_TABSTOP,24,570,620,80,ID_FAIR_SUMMARY);

 d->creatingPage=5;
 label(d,"Exploration and visibility",24,108,632,24);
 label(d,"Map visibility",24,150,620,22);
 fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,176,620,180,ID_MAP_VISIBILITY),visibility,3,1);
 label(d,"Enemy activity",24,236,620,22);
 fillCombo(control(d,"COMBOBOX","",CBS_DROPDOWNLIST|WS_TABSTOP|WS_VSCROLL,24,262,620,150,ID_ENEMY_VISIBILITY),enemies,2,0);
 label(d,"Unexplored covers this preview and uncharted land and sea. Ships, settlements and deployed military units chart nearby areas, which stay remembered. Geography revealed shows island locations; Fully explored charts the whole map.\r\n\r\nStrict line of sight hides moving units beyond 48 tiles of your ships, settlements or deployed military units. Buildings stay as last seen until revisited. Reveal all activity shows live activity in charted areas. Both keep unexplored areas covered.\r\n\r\nOlder saves without exploration history start around your current units; buildings are remembered as you see them. Preferred climates and balanced starts still work; Unexplored disables preview island selection.",24,332,620,280);

 d->creatingPage=-1;
 label(d,"Map seed",688,58,408,20);control(d,"EDIT","",WS_BORDER|ES_NUMBER|WS_TABSTOP,688,82,280,28,ID_SEED);SendDlgItemMessageA(w,ID_SEED,EM_SETLIMITTEXT,10,0);
 control(d,"BUTTON","Copy seed",BS_PUSHBUTTON|WS_TABSTOP,980,82,116,28,ID_COPY_SEED);
 d->preview=CreateWindowExA(0,previewClassName,"",WS_CHILD|WS_VISIBLE|WS_BORDER,scaled(d,688),scaled(d,136),scaled(d,408),scaled(d,408),w,(HMENU)(INT_PTR)ID_PREVIEW,dllInstance,d);
 if(!d->preview)return 0;
 control(d,"STATIC","",SS_LEFT,688,558,408,40,ID_START_HINT);
 for(int i=0;i<6;i++)label(d,previewClimateNames[i],710+(i%2)*212,610+(i/2)*24,174,20);
 label(d,"P: Pirates   V: Venetians   S: human   1-3: AI",688,692,408,24);
 control(d,"BUTTON","Regenerate map",BS_PUSHBUTTON|WS_TABSTOP,688,726,196,32,ID_REGENERATE);
 label(d,"Same seed + same world options reproduce the preview.",896,726,200,38);
 label(d,"Status",24,670,632,20);control(d,"STATIC",developmentConfigured&&prepareBackend?configuredStatus:noBackend,SS_LEFT,24,696,632,64,ID_STATUS);
 control(d,"BUTTON","Back",BS_PUSHBUTTON|WS_TABSTOP,388,768,120,32,ID_BACK);control(d,"BUTTON","Start",BS_DEFPUSHBUTTON|WS_TABSTOP,528,768,120,32,ID_START);
 wsMenuPutSeed(d,freshPreviewSeed(0));wsMenuCargoControls(d);wsMenuFairControls(d);wsMenuActivityControls(d);wsMenuStartHint(d);wsMenuIslandInfo(d);wsPresetRefresh(d,NULL);wsMenuPage(d,0);
 EnableWindow(GetDlgItem(w,ID_START),FALSE);d->creating=0;PostMessageA(w,WS_PREVIEW_MESSAGE,0,0);
 SetFocus(GetDlgItem(w,ID_WORLD_SIZE));return 1;
}
