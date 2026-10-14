    // ===== 参数 (输入均带 double 类型提示, 直接使用) =====
    double OPEN  = opening;    // 井口净空
    double TD    = trayDepth;  // 托盘深度
    double GAP   = gap;        // 托盘-外框缝隙
    double LIP   = lip;        // 外框可见边
    double FT    = frameT;     // 外框板厚
    double WT    = wallT;      // 托盘壁厚
    double PLT   = plateT;     // 镀锌底板厚
    int    RN    = (int) Math.Round(ribCount); // 肋网格 NxN
    double RT    = ribT;       // 肋厚
    double RH    = ribH;       // 肋高
    double RINGT = ringT;      // 井圈壁厚
    double RINGD = ringD;      // 井圈深度
    double PT    = pavingT;    // 铺装厚

    if(RN < 1) RN = 1;

    // ===== 水平坐标(半宽, 中心为0) =====
    double OH         = OPEN / 2.0;
    double X_WEB_OUT  = OH + 20;            // 外框腹板外缘
    double X_BAND_IN  = X_WEB_OUT - FT;     // 腹板内缘/顶唇内缘
    double X_LEDGE_IN = X_BAND_IN - 16;     // 承托内缘
    double X_RIM_OUT  = X_BAND_IN - GAP;    // 托盘翻边外缘
    double X_WALL_OUT = X_RIM_OUT - 26;     // 托盘壁外缘
    double X_PAV_IN   = X_WALL_OUT - WT;    // 托盘内腔半宽
    double X_LIP_OUT  = X_BAND_IN + LIP;    // 顶唇外缘=周边铺装内缘
    double X_FRAME_OUT= X_WEB_OUT + RINGT;  // 外框/井圈外缘
    double X_SURR_OUT = X_LIP_OUT + 600;    // 周边铺装外缘

    // ===== 竖向坐标(z=0 完成面) =====
    double zLipB   = -FT;
    double zLedgeB = -FT - 8;
    double zWebB   = -(PT + 25);
    double zFlgB   = zWebB - FT;
    double zRingB  = zFlgB - RINGD;
    double zPadT   = zLedgeB;
    double zPadB   = zPadT - 8;
    double zRimT   = zPadB;
    double zRimB   = zRimT - 10;
    double zPlateT = -(TD - PLT);
    double zPlateB = -TD;
    double zRibB   = zPlateB - RH;
    double zMesh   = (zPlateT - PT) / 2.0;

    var frame = new List<Brep>();  var tray  = new List<Brep>();
    var plate = new List<Brep>();  var mesh  = new List<Brep>();
    var mortar= new List<Brep>();  var paving= new List<Brep>();
    var ribs  = new List<Brep>();  var pads  = new List<Brep>();
    var holes = new List<Brep>();  var ring  = new List<Brep>();

    // 外框 Z形截面: 顶唇+承托+腹板+底部法兰
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_LIP_OUT, X_BAND_IN, zLipB, X_LIP_OUT, X_LIP_OUT, 0)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_LIP_OUT, -X_LIP_OUT, zLipB, X_LIP_OUT, -X_BAND_IN, 0)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(X_BAND_IN, -X_BAND_IN, zLipB, X_LIP_OUT, X_BAND_IN, 0)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_LIP_OUT, -X_BAND_IN, zLipB, -X_BAND_IN, X_BAND_IN, 0)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_BAND_IN, X_LEDGE_IN, zLedgeB, X_BAND_IN, X_BAND_IN, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_BAND_IN, -X_BAND_IN, zLedgeB, X_BAND_IN, -X_LEDGE_IN, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(X_LEDGE_IN, -X_LEDGE_IN, zLedgeB, X_BAND_IN, X_LEDGE_IN, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_BAND_IN, -X_LEDGE_IN, zLedgeB, -X_LEDGE_IN, X_LEDGE_IN, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_WEB_OUT, X_BAND_IN, zWebB, X_WEB_OUT, X_WEB_OUT, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_WEB_OUT, -X_WEB_OUT, zWebB, X_WEB_OUT, -X_BAND_IN, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(X_BAND_IN, -X_BAND_IN, zWebB, X_WEB_OUT, X_BAND_IN, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_WEB_OUT, -X_BAND_IN, zWebB, -X_BAND_IN, X_BAND_IN, -FT)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_FRAME_OUT, X_WEB_OUT, zFlgB, X_FRAME_OUT, X_FRAME_OUT, zWebB)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_FRAME_OUT, -X_FRAME_OUT, zFlgB, X_FRAME_OUT, -X_WEB_OUT, zWebB)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(X_WEB_OUT, -X_WEB_OUT, zFlgB, X_FRAME_OUT, X_WEB_OUT, zWebB)));
    frame.Add(Brep.CreateFromBox(new BoundingBox(-X_FRAME_OUT, -X_WEB_OUT, zFlgB, -X_WEB_OUT, X_WEB_OUT, zWebB)));
    // 托盘: 翻边+壁
    tray.Add(Brep.CreateFromBox(new BoundingBox(-X_RIM_OUT, X_WALL_OUT, zRimB, X_RIM_OUT, X_RIM_OUT, zRimT)));
    tray.Add(Brep.CreateFromBox(new BoundingBox(-X_RIM_OUT, -X_RIM_OUT, zRimB, X_RIM_OUT, -X_WALL_OUT, zRimT)));
    tray.Add(Brep.CreateFromBox(new BoundingBox(X_WALL_OUT, -X_WALL_OUT, zRimB, X_RIM_OUT, X_WALL_OUT, zRimT)));
    tray.Add(Brep.CreateFromBox(new BoundingBox(-X_RIM_OUT, -X_WALL_OUT, zRimB, -X_WALL_OUT, X_WALL_OUT, zRimT)));
    tray.Add(Brep.CreateFromBox(new BoundingBox(-X_WALL_OUT, X_PAV_IN, zPlateT, X_WALL_OUT, X_WALL_OUT, -4)));
    tray.Add(Brep.CreateFromBox(new BoundingBox(-X_WALL_OUT, -X_WALL_OUT, zPlateT, X_WALL_OUT, -X_PAV_IN, -4)));
    tray.Add(Brep.CreateFromBox(new BoundingBox(X_PAV_IN, -X_PAV_IN, zPlateT, X_WALL_OUT, X_PAV_IN, -4)));
    tray.Add(Brep.CreateFromBox(new BoundingBox(-X_WALL_OUT, -X_PAV_IN, zPlateT, -X_PAV_IN, X_PAV_IN, -4)));
    // 镀锌底板 / 钢网 / 托盘内砂浆 / 托盘内铺装
    plate.Add(Brep.CreateFromBox(new BoundingBox(-X_WALL_OUT, -X_WALL_OUT, zPlateB, X_WALL_OUT, X_WALL_OUT, zPlateT)));
    mesh.Add(Brep.CreateFromBox(new BoundingBox(-X_PAV_IN, -X_PAV_IN, zMesh - 1, X_PAV_IN, X_PAV_IN, zMesh + 1)));
    mortar.Add(Brep.CreateFromBox(new BoundingBox(-X_PAV_IN, -X_PAV_IN, zPlateT, X_PAV_IN, X_PAV_IN, -PT)));
    paving.Add(Brep.CreateFromBox(new BoundingBox(-X_PAV_IN, -X_PAV_IN, -PT, X_PAV_IN, X_PAV_IN, 0)));
    // 加强肋 NxN
    for(int i = 0; i < RN; i++){
      double p = -X_WALL_OUT + (i + 0.5) * (2 * X_WALL_OUT / RN);
      ribs.Add(Brep.CreateFromBox(new BoundingBox(-X_WALL_OUT, p - RT / 2, zRibB, X_WALL_OUT, p + RT / 2, zPlateB)));
      ribs.Add(Brep.CreateFromBox(new BoundingBox(p - RT / 2, -X_WALL_OUT, zRibB, p + RT / 2, X_WALL_OUT, zPlateB)));
    }
    // 橡胶垫块 6块
    double pa = X_WALL_OUT * 0.54, pb = X_RIM_OUT - 6;
    double[,] pp = {{-pa, pb}, {pa, pb}, {-pa, -pb}, {pa, -pb}, {pb, 0}, {-pb, 0}};
    for(int i = 0; i < 6; i++)
      pads.Add(Brep.CreateFromBox(new BoundingBox(pp[i, 0] - 12, pp[i, 1] - 12, zPadB, pp[i, 0] + 12, pp[i, 1] + 12, zPadT)));
    // 开启槽 4角
    double hc = X_PAV_IN - 35;
    double[,] hp = {{hc, hc}, {hc, -hc}, {-hc, hc}, {-hc, -hc}};
    for(int i = 0; i < 4; i++)
      holes.Add(Brep.CreateFromBox(new BoundingBox(hp[i, 0] - 25, hp[i, 1] - 7, -6, hp[i, 0] + 25, hp[i, 1] + 7, -1)));

    // 混凝土井圈
    ring.Add(Brep.CreateFromBox(new BoundingBox(-X_FRAME_OUT, X_WEB_OUT, zRingB, X_FRAME_OUT, X_FRAME_OUT, zFlgB)));
    ring.Add(Brep.CreateFromBox(new BoundingBox(-X_FRAME_OUT, -X_FRAME_OUT, zRingB, X_FRAME_OUT, -X_WEB_OUT, zFlgB)));
    ring.Add(Brep.CreateFromBox(new BoundingBox(X_WEB_OUT, -X_WEB_OUT, zRingB, X_FRAME_OUT, X_WEB_OUT, zFlgB)));
    ring.Add(Brep.CreateFromBox(new BoundingBox(-X_FRAME_OUT, -X_WEB_OUT, zRingB, -X_WEB_OUT, X_WEB_OUT, zFlgB)));
    // 周边铺装+砂浆
    paving.Add(Brep.CreateFromBox(new BoundingBox(-X_SURR_OUT, X_LIP_OUT, -PT, X_SURR_OUT, X_SURR_OUT, 0)));
    paving.Add(Brep.CreateFromBox(new BoundingBox(-X_SURR_OUT, -X_SURR_OUT, -PT, X_SURR_OUT, -X_LIP_OUT, 0)));
    paving.Add(Brep.CreateFromBox(new BoundingBox(X_LIP_OUT, -X_LIP_OUT, -PT, X_SURR_OUT, X_LIP_OUT, 0)));
    paving.Add(Brep.CreateFromBox(new BoundingBox(-X_SURR_OUT, -X_LIP_OUT, -PT, -X_LIP_OUT, X_LIP_OUT, 0)));
    mortar.Add(Brep.CreateFromBox(new BoundingBox(-X_SURR_OUT, X_LIP_OUT, zWebB, X_SURR_OUT, X_SURR_OUT, -PT)));
    mortar.Add(Brep.CreateFromBox(new BoundingBox(-X_SURR_OUT, -X_SURR_OUT, zWebB, X_SURR_OUT, -X_LIP_OUT, -PT)));
    mortar.Add(Brep.CreateFromBox(new BoundingBox(X_LIP_OUT, -X_LIP_OUT, zWebB, X_SURR_OUT, X_LIP_OUT, -PT)));
    mortar.Add(Brep.CreateFromBox(new BoundingBox(-X_SURR_OUT, -X_LIP_OUT, zWebB, -X_LIP_OUT, X_LIP_OUT, -PT)));

    Frame = frame; Tray = tray; Plate = plate; Mesh = mesh; Mortar = mortar;
    Paving = paving; Ribs = ribs; Pads = pads; Holes = holes; Ring = ring;
    Print("隐形井盖构件总数: " + (frame.Count + tray.Count + plate.Count + mesh.Count
      + mortar.Count + paving.Count + ribs.Count + pads.Count + holes.Count + ring.Count).ToString());