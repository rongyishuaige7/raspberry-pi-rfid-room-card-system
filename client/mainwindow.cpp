#include "mainwindow.h"
#include "roomlabel.h"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QMessageBox>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QDebug>
#include <QGroupBox>
#include <QLabel>
#include <QDate>
#include <QFileDialog>
#include <QFile>
#include <QTextStream>
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
#include <QStringConverter>
#endif
#include <QScrollArea>
#include <QDateTime>
#include <QListWidget>
#include <QListWidgetItem>
#include <QMouseEvent>
#include "ui_mainwindow.h"

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
    , m_network(new Network(this))
    , m_cardSelected(false)
{
    ui->setupUi(this);
    setupUI();

    connect(m_network, &Network::errorOccurred, this, &MainWindow::onNetworkError);
}

void MainWindow::setNetwork(Network *net)
{
    // 将传入的全局 Network 对象赋值给成员变量
    m_network = net;

    // 同步显示当前连接的 IP 和端口
    if (m_network) {
        // UI 编辑框反显当前的网络配置
        m_hostEdit->setText(m_network->host());
        m_portEdit->setText(QString::number(m_network->port()));
    }

    // 重新连接信号
    connect(m_network, &Network::connected, this, &MainWindow::onNetworkConnected);
    connect(m_network, &Network::disconnected, this, &MainWindow::onNetworkDisconnected);
    connect(m_network, &Network::errorOccurred, this, &MainWindow::onNetworkError);
    connect(m_network, &Network::responseReady, this, &MainWindow::onResponseReady);

    // 初始化实时刷新定时器
    m_refreshTimer = new QTimer(this);
    m_refreshTimer->setInterval(60000); // 1分钟刷新一次
    connect(m_refreshTimer, &QTimer::timeout, this, [this](){
        if (m_network && m_network->isConnected())
            refreshRoomList();
    });
    m_lastLogId = 0;

    // 如果已经连接，直接更新状态
    if (m_network->isConnected()) {
        onNetworkConnected();
    }
}

MainWindow::~MainWindow()
{
    delete ui;
}

void MainWindow::setupUI()
{
    setWindowTitle("房卡管理系统");
    resize(1450, 850);
    setMinimumSize(1000, 750);

    // 设置全局 QSS 样式
    QString qss =
        "QMainWindow { background-color: #f5f7fa; }"
        "QGroupBox { font-weight: bold; border: 1px solid #dcdfe6; border-radius: 6px; margin-top: 12px; padding-top: 15px; background-color: white; }"
        "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; left: 15px; padding: 0 5px; color: #409eff; }"
        "QPushButton { border-radius: 4px; padding: 6px 12px; font-weight: 500; min-height: 28px; border: 1px solid #dcdfe6; background-color: white; }"
        "QPushButton:hover { background-color: #ecf5ff; color: #409eff; border-color: #c6e2ff; }"
        "QPushButton:pressed { background-color: #d9ecff; }"
        "QPushButton:disabled { background-color: #f5f7fa; color: #c0c4cc; border-color: #ebeef5; }"
        // 特定按钮样式
        "#connectBtn[connected=\"true\"] { background-color: #fef0f0; color: #f56c6c; border-color: #fbc4c4; }"
        "#connectBtn[connected=\"true\"]:hover { background-color: #f56c6c; color: white; }"
        "#addCardBtn { background-color: #409eff; color: white; border: none; }"
        "#addCardBtn:hover { background-color: #66b1ff; }"
        "#openDoorBtn { background-color: #67c23a; color: white; border: none; }"
        "#openDoorBtn:hover { background-color: #85ce61; }"
        "#deleteCardBtn, #cancelCardBtn { color: #f56c6c; }"
        "#deleteCardBtn:hover, #cancelCardBtn:hover { background-color: #fef0f0; border-color: #fbc4c4; }"
        "QLineEdit, QComboBox, QDateEdit { border: 1px solid #dcdfe6; border-radius: 4px; padding: 4px 8px; background: white; }"
        "QLineEdit:focus, QComboBox:focus { border-color: #409eff; }"
        "QTableWidget { border: 1px solid #dcdfe6; background-color: white; alternate-background-color: #fafafa; selection-background-color: #ecf5ff; selection-color: #409eff; outline: none; }"
        "QHeaderView::section { background-color: #f8f9fa; padding: 6px; border: none; border-bottom: 1px solid #dcdfe6; font-weight: bold; color: #606266; }"
        "QTabWidget::pane { border: 1px solid #dcdfe6; top: -1px; background: white; }"
        "QTabBar::tab { background: #f5f7fa; border: 1px solid #dcdfe6; padding: 8px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }"
        "QTabBar::tab:selected { background: white; border-bottom-color: white; color: #409eff; font-weight: bold; }"
        "QLabel#statusIcon { border-radius: 6px; background-color: #909399; }"
    ;
    this->setStyleSheet(qss);

    QWidget *centralWidget = new QWidget(this);
    setCentralWidget(centralWidget);
    QVBoxLayout *mainLayout = new QVBoxLayout(centralWidget);
    mainLayout->setContentsMargins(15, 15, 15, 15);
    mainLayout->setSpacing(15);

    // === 顶部栏：连接与统计 ===
    QWidget *topBar = new QWidget(this);
    topBar->setObjectName("topBar");
    topBar->setStyleSheet("QWidget#topBar { background-color: white; border-radius: 8px; border: 1px solid #dcdfe6; }");
    QHBoxLayout *topLayout = new QHBoxLayout(topBar);
    topLayout->setContentsMargins(15, 10, 15, 10);

    // 连接部分
    QHBoxLayout *connSubLayout = new QHBoxLayout();
    connSubLayout->setSpacing(10);
    connSubLayout->addWidget(new QLabel("服务器:", this));
    m_hostEdit = new QLineEdit("127.0.0.1", this);
    m_hostEdit->setFixedWidth(130);
    m_hostEdit->setPlaceholderText("IP地址");
    connSubLayout->addWidget(m_hostEdit);

    m_portEdit = new QLineEdit("8888", this);
    m_portEdit->setFixedWidth(60);
    m_portEdit->setPlaceholderText("端口");
    connSubLayout->addWidget(m_portEdit);

    m_connectBtn = new QPushButton("连接服务器", this);
    m_connectBtn->setObjectName("connectBtn");
    m_connectBtn->setFixedWidth(100);
    connSubLayout->addWidget(m_connectBtn);

    m_statusLabel = new QLabel("未连接", this);
    m_statusLabel->setMinimumWidth(80); // 增加宽度，防止重叠
    m_statusLabel->setAlignment(Qt::AlignCenter);
    m_statusLabel->setStyleSheet("color: #909399; font-weight: bold; margin-left: 5px;");
    connSubLayout->addWidget(m_statusLabel);

    topLayout->addLayout(connSubLayout);
    topLayout->addStretch();

    // 用户信息与退出登录
    m_userLabel = new QLabel(this);
    m_userLabel->setStyleSheet("color: #409eff; font-weight: bold; margin-right: 15px;");
    topLayout->addWidget(m_userLabel);

    m_logoutBtn = new QPushButton("退出登录", this);
    m_logoutBtn->setFixedWidth(85);
    m_logoutBtn->setCursor(Qt::PointingHandCursor);
    m_logoutBtn->setStyleSheet(
        "QPushButton { color: #f56c6c; border: 1px solid #fbc4c4; background-color: #fef0f0; }"
        "QPushButton:hover { background-color: #f56c6c; color: white; }"
    );
    topLayout->addWidget(m_logoutBtn);

    // 统计部分
    m_statsLabel = new QLabel("系统概览: 等待连接...", this);
    m_statsLabel->setStyleSheet("color: #606266; padding: 5px 15px; background: #f0f2f5; border-radius: 15px;");
    topLayout->addWidget(m_statsLabel);

    mainLayout->addWidget(topBar);

    // === 中间内容区：采用水平分栏或分页 ===
    QHBoxLayout *contentLayout = new QHBoxLayout();

    // 左侧：操作面板
    QVBoxLayout *leftLayout = new QVBoxLayout();

    // 发卡/读卡区域
    QGroupBox *opGroup = new QGroupBox("房卡业务操作", this);
    QVBoxLayout *opLayout = new QVBoxLayout(opGroup);
    opLayout->setSpacing(12);

    auto createFormField = [&](const QString &label, QWidget *widget) {
        QHBoxLayout *l = new QHBoxLayout();
        QLabel *lbl = new QLabel(label, this);
        lbl->setFixedWidth(65);
        l->addWidget(lbl);
        l->addWidget(widget);
        return l;
    };

    m_uidEdit = new QLineEdit(this);
    m_uidEdit->setPlaceholderText("请先读卡或手动输入UID");
    m_uidEdit->setMinimumWidth(220); // 增加长度，确保完整看到UID
    m_readCardBtn = new QPushButton("读卡", this);
    m_readCardBtn->setFixedWidth(70);
    QHBoxLayout *uidLayout = createFormField("卡片UID:", m_uidEdit);
    uidLayout->addWidget(m_readCardBtn);
    opLayout->addLayout(uidLayout);

    m_roomCombo = new QComboBox(this);
    opLayout->addLayout(createFormField("下发房间:", m_roomCombo));

    m_expireDateEdit = new QDateEdit(this);
    m_expireDateEdit->setCalendarPopup(true);
    m_expireDateEdit->setDate(QDate::currentDate().addDays(1)); // 默认明天
    opLayout->addLayout(createFormField("有效截止:", m_expireDateEdit));

    opLayout->addSpacing(10);

    // 功能按钮网关
    QGridLayout *gridBtn = new QGridLayout();
    m_addCardBtn = new QPushButton("立即发卡", this);
    m_addCardBtn->setObjectName("addCardBtn");
    m_addCardBtn->setFixedHeight(40);

    m_openDoorBtn = new QPushButton("远程开门", this);
    m_openDoorBtn->setObjectName("openDoorBtn");
    m_openDoorBtn->setFixedHeight(40);

    gridBtn->addWidget(m_addCardBtn, 0, 0);
    gridBtn->addWidget(m_openDoorBtn, 0, 1);

    m_checkCardBtn = new QPushButton("状态查询", this);
    m_lostCardBtn = new QPushButton("挂失卡片", this);
    m_lostCardBtn->setObjectName("lostCardBtn");
    m_cancelCardBtn = new QPushButton("注销退房", this);
    m_cancelCardBtn->setObjectName("cancelCardBtn");
    m_deleteCardBtn = new QPushButton("记录删除", this);
    m_deleteCardBtn->setObjectName("deleteCardBtn");

    gridBtn->addWidget(m_checkCardBtn, 1, 0);
    gridBtn->addWidget(m_lostCardBtn, 1, 1);
    gridBtn->addWidget(m_cancelCardBtn, 2, 0);
    gridBtn->addWidget(m_deleteCardBtn, 2, 1);

    opLayout->addLayout(gridBtn);

    m_refreshBtn = new QPushButton("同步数据", this);
    m_refreshBtn->setIcon(style()->standardIcon(QStyle::SP_BrowserReload));

    m_exportBtn = new QPushButton("导出报表", this);
    m_exportBtn->setIcon(style()->standardIcon(QStyle::SP_DialogSaveButton));

    QHBoxLayout *bottomBtnLayout = new QHBoxLayout();
    bottomBtnLayout->addWidget(m_refreshBtn);
    bottomBtnLayout->addWidget(m_exportBtn);
    opLayout->addLayout(bottomBtnLayout);

    leftLayout->addWidget(opGroup);
    leftLayout->addStretch();
    contentLayout->addLayout(leftLayout, 1);

    // 右侧：表格展示（采用 Tab 分页）
    QTabWidget *tabWidget = new QTabWidget(this);

    // 房卡列表分页
    QWidget *cardTabPage = new QWidget();
    QVBoxLayout *cardTabLayout = new QVBoxLayout(cardTabPage);

    // 搜索栏
    QHBoxLayout *searchLayout = new QHBoxLayout();
    m_searchEdit = new QLineEdit(this);
    m_searchEdit->setPlaceholderText("🔍 输入房号或UID快速检索...");
    m_searchEdit->setClearButtonEnabled(true);
    searchLayout->addWidget(m_searchEdit);
    cardTabLayout->addLayout(searchLayout);

    m_cardTable = new QTableWidget(this);
    setupCardTable();
    cardTabLayout->addWidget(m_cardTable);
    tabWidget->addTab(cardTabPage, "当前有效房卡");

    // 日志分页
    QWidget *logTabPage = new QWidget();
    QVBoxLayout *logTabLayout = new QVBoxLayout(logTabPage);
    m_logTable = new QTableWidget(this);
    setupLogTable();
    logTabLayout->addWidget(m_logTable);
    tabWidget->addTab(logTabPage, "系统安全日志");

    m_tabWidget = tabWidget;
    contentLayout->addWidget(m_tabWidget, 3); // 增加权重占中间大头

    // 数据分析分页 (毕设演示用)
    m_analysisTab = new QWidget();
    QVBoxLayout *analysisLayout = new QVBoxLayout(m_analysisTab);
    analysisLayout->setContentsMargins(40, 40, 40, 40);
    analysisLayout->setSpacing(30);

    QLabel *anaHeader = new QLabel("房卡系统运营数据实时看板", m_analysisTab);
    anaHeader->setStyleSheet("font-size: 24px; font-weight: bold; color: #303133; margin-bottom: 10px;");
    analysisLayout->addWidget(anaHeader);

    QGridLayout *statGrid = new QGridLayout();
    statGrid->setSpacing(30);

    QStringList titles = {"总发行卡量", "活跃使用卡", "挂失异常卡", "今日开门任务"};
    QStringList colors = {"#409eff", "#67c23a", "#e6a23c", "#f56c6c"};
    QStringList subtexts = {"系统累计签发房卡总数", "当前处于正常持卡状态", "需要关注的丢失或冻结卡项", "24小时内刷卡开门频次"};

    for(int i=0; i<4; ++i) {
        QFrame *card = new QFrame(m_analysisTab);
        card->setObjectName("anaCard");
        card->setFixedSize(280, 180);

        // 改进后的现代样式表 (白色背景 + 侧边彩色装饰条)
        card->setStyleSheet(QString(
            "QFrame#anaCard { "
            "  background-color: white; "
            "  border-radius: 15px; "
            "  border: 1px solid #ebeef5; "
            "} "
        ));

        QVBoxLayout *cl = new QVBoxLayout(card);
        cl->setContentsMargins(20, 20, 20, 20);

        // 顶部水平布局：标题 + 彩色指示圆点
        QHBoxLayout *hl = new QHBoxLayout();
        QLabel *dot = new QLabel("●", card);
        dot->setStyleSheet(QString("color: %1; font-size: 16px;").arg(colors[i]));
        hl->addWidget(dot);

        QLabel *tl = new QLabel(titles[i], card);
        tl->setStyleSheet("color: #606266; font-size: 15px; font-weight: bold;");
        hl->addWidget(tl);
        hl->addStretch();
        cl->addLayout(hl);

        // 中间大数字
        m_analysisStats[i] = new QLabel("0", card);
        m_analysisStats[i]->setStyleSheet(QString("color: %1; font-size: 48px; font-weight: 800; font-family: 'Segoe UI', Arial;").arg(titles[i] == "挂失异常卡" ? "#f56c6c" : "#303133"));
        m_analysisStats[i]->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
        cl->addWidget(m_analysisStats[i]);

        // 底部辅助文字
        QLabel *sl = new QLabel(subtexts[i], card);
        sl->setStyleSheet("color: #909399; font-size: 12px;");
        cl->addWidget(sl);

        statGrid->addWidget(card, i/2, i%2, Qt::AlignCenter);
    }
    analysisLayout->addLayout(statGrid);
    analysisLayout->addStretch();

    m_tabWidget->addTab(m_analysisTab, "数据分析看板");

    // 房间地图分页
    m_roomTab = new QWidget();
    QVBoxLayout *roomTabLayout = new QVBoxLayout(m_roomTab);
    QLabel *roomHeader = new QLabel("酒店客房实时状态分布图", m_roomTab);
    roomHeader->setStyleSheet("font-size: 18px; font-weight: bold; color: #303133; margin-bottom: 10px;");
    roomTabLayout->addWidget(roomHeader);

    QScrollArea *scroll = new QScrollArea(m_roomTab);
    scroll->setWidgetResizable(true);
    scroll->setStyleSheet("QScrollArea { border: none; background: transparent; }");
    QWidget *container = new QWidget();
    m_roomLayout = new QGridLayout(container);
    m_roomLayout->setSpacing(15);
    scroll->setWidget(container);
    roomTabLayout->addWidget(scroll);

    m_tabWidget->insertTab(1, m_roomTab, "客房状态分布图");

    // === 右侧：实时监控流 (移到侧边填补空白) ===
    m_monitorGroup = new QGroupBox("系统实时监控流 (Live Monitor)", this);
    m_monitorGroup->setFixedWidth(280); // 固定宽度作为右侧栏
    QVBoxLayout *monitorLayout = new QVBoxLayout(m_monitorGroup);
    m_liveMonitor = new QListWidget(this);
    m_liveMonitor->setStyleSheet(
        "QListWidget { border: none; background: #2c3e50; color: #ecf0f1; font-family: 'Courier New'; font-size: 11px; }"
    );
    monitorLayout->addWidget(m_liveMonitor);
    contentLayout->addWidget(m_monitorGroup);

    mainLayout->addLayout(contentLayout);

    // 状态栏
    statusBar()->showMessage("就绪");
    statusBar()->setStyleSheet("color: #909399; font-size: 11px;");

    // 连接信号
    connect(m_connectBtn, &QPushButton::clicked, this, &MainWindow::onConnectClicked);
    connect(m_readCardBtn, &QPushButton::clicked, this, &MainWindow::onReadCardClicked);
    connect(m_addCardBtn, &QPushButton::clicked, this, &MainWindow::onAddCardClicked);
    connect(m_openDoorBtn, &QPushButton::clicked, this, &MainWindow::onOpenDoorClicked);
    connect(m_checkCardBtn, &QPushButton::clicked, this, &MainWindow::onCheckCardClicked);
    connect(m_lostCardBtn, &QPushButton::clicked, this, &MainWindow::onLostCardClicked);
    connect(m_cancelCardBtn, &QPushButton::clicked, this, &MainWindow::onCancelCardClicked);
    connect(m_deleteCardBtn, &QPushButton::clicked, this, &MainWindow::onDeleteCardClicked);
    connect(m_refreshBtn, &QPushButton::clicked, this, &MainWindow::onRefreshClicked);
    connect(m_exportBtn, &QPushButton::clicked, this, &MainWindow::onExportClicked);
    connect(m_logoutBtn, &QPushButton::clicked, this, &MainWindow::onLogoutClicked);
    connect(m_searchEdit, &QLineEdit::textChanged, this, &MainWindow::onSearchTextChanged);
    connect(m_cardTable, &QTableWidget::cellClicked, this, &MainWindow::onCardTableClicked);

    setControlsEnabled(false);
}

void MainWindow::setUserRole(const QString &role, const QString &username)
{
    m_role = role;
    m_username = username;

    QString roleText;
    if (role == "Admin") roleText = "系统管理员";
    else if (role == "FrontDesk") roleText = "前台接待";
    else if (role == "Housekeeping") roleText = "客房保洁";

    m_userLabel->setText(QString("当前用户: %1 (%2)").arg(username, roleText));

    // RBAC 权限控制
    if (role == "Housekeeping") {
        m_addCardBtn->setVisible(false);
        m_lostCardBtn->setVisible(false);
        m_cancelCardBtn->setVisible(false);
        m_deleteCardBtn->setVisible(false);
        m_uidEdit->setReadOnly(true);
        m_roomCombo->setEnabled(false);
        m_expireDateEdit->setEnabled(false);
        m_readCardBtn->setVisible(false);

        // 隐藏不该看的 Tab
        for(int i=0; i<m_tabWidget->count(); ++i) {
            if (m_tabWidget->tabText(i) == "系统安全日志" || m_tabWidget->tabText(i) == "数据分析看板") {
                m_tabWidget->removeTab(i--);
            }
        }

        // 保洁不需要实时监控流
        m_monitorGroup->setVisible(false);
    } else if (role == "FrontDesk") {
        m_deleteCardBtn->setVisible(false); // 前台不允许彻底删除，只能注销

        // 前台不需要显示日志和看板
        for(int i=0; i<m_tabWidget->count(); ++i) {
            QString text = m_tabWidget->tabText(i);
            if (text == "系统安全日志" || text == "数据分析看板") {
                m_tabWidget->removeTab(i--);
            }
        }
        m_monitorGroup->setVisible(false);
    } else {
        // Admin
        m_monitorGroup->setVisible(true);
    }
}

void MainWindow::setControlsEnabled(bool enabled)
{
    m_readCardBtn->setEnabled(enabled);
    m_addCardBtn->setEnabled(enabled);
    m_openDoorBtn->setEnabled(enabled);
    m_checkCardBtn->setEnabled(enabled);
    m_lostCardBtn->setEnabled(enabled);
    m_cancelCardBtn->setEnabled(enabled);
    m_deleteCardBtn->setEnabled(enabled);
    m_refreshBtn->setEnabled(enabled);
    m_uidEdit->setEnabled(enabled);
    m_roomCombo->setEnabled(enabled);
    m_expireDateEdit->setEnabled(enabled);
}

void MainWindow::onConnectClicked()
{
    if (m_network->isConnected()) {
        m_network->disconnect();
    } else {
        QString host = m_hostEdit->text();
        quint16 port = m_portEdit->text().toUShort();
        if (host.isEmpty()) {
            showMessage("请输入服务器IP", true);
            return;
        }
        m_network->connectToServer(host, port);
    }
}

void MainWindow::onExportClicked()
{
    QString fileName = QFileDialog::getSaveFileName(this, "导出日志数据",
                                                    QDate::currentDate().toString("yyyy-MM-dd") + "_logs.csv",
                                                    "CSV文件 (*.csv)");
    if (fileName.isEmpty()) return;

    QFile file(fileName);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        showMessage("无法创建文件", true);
        return;
    }

    QTextStream out(&file);
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
    out.setEncoding(QStringConverter::Utf8);
#else
    out.setCodec("UTF-8");
#endif
    out << (unsigned char)0xEF << (unsigned char)0xBB << (unsigned char)0xBF;

    out << "ID,卡号,操作类型,操作员,结果,详情,时间\n";
    for (int i = 0; i < m_logTable->rowCount(); ++i) {
        QStringList row;
        // 映射出正确的CSV列顺序: ID, 卡号, 操作, 操作员, 结果, 详情, 时间
        // 原列: 0:ID, 1:时间, 2:卡号, 3:操作, 4:操作员, 5:结果, 6:详情
        row.append(m_logTable->item(i, 0)->text());
        row.append(m_logTable->item(i, 2)->text());
        row.append(m_logTable->item(i, 3)->text());
        row.append(m_logTable->item(i, 4)->text());
        row.append(m_logTable->item(i, 5)->text());
        row.append(m_logTable->item(i, 6)->text());
        row.append(m_logTable->item(i, 1)->text());
        out << row.join(",") << "\n";
    }
    file.close();
    QMessageBox::information(this, "导出成功", "日志已成功导出至:\n" + fileName);
    addLiveEvent("导出安全日志报表成功: " + fileName.section('/', -1));
}

void MainWindow::addLiveEvent(const QString &text, bool critical)
{
    QString timeStr = QDateTime::currentDateTime().toString("HH:mm:ss");
    QListWidgetItem *item = new QListWidgetItem(QString("[%1] %2").arg(timeStr, text));
    if (critical) {
        item->setForeground(QColor("#f56c6c"));
    } else {
        item->setForeground(QColor("#67c23a"));
    }
    m_liveMonitor->insertItem(0, item);
    if (m_liveMonitor->count() > 50) {
        delete m_liveMonitor->takeItem(m_liveMonitor->count() - 1);
    }
}

void MainWindow::onLogoutClicked()
{
    if (QMessageBox::question(this, "退出确认", "确定要登出当前账号并返回登录界面吗？") == QMessageBox::Yes) {
        emit logoutRequested();
        this->close();
    }
}

void MainWindow::onSearchTextChanged(const QString &text)
{
    QString filter = text.toLower();
    for (int i = 0; i < m_cardTable->rowCount(); ++i) {
        bool match = false;
        // 搜索UID和房间号列 (col 1 and col 3 in table)
        if (m_cardTable->item(i, 0)->text().toLower().contains(filter) ||
            m_cardTable->item(i, 2)->text().toLower().contains(filter)) {
            match = true;
        }
        m_cardTable->setRowHidden(i, !match);
    }
}

void MainWindow::onNetworkConnected()
{
    updateConnectionStatus(true);
    showMessage("连接成功");
    refreshRoomList();  // 启动刷新链: GetRooms -> GetCards -> GetLogs -> GetStats
    addLiveEvent("已连接房卡服务端");
    m_refreshTimer->start();
}

void MainWindow::onNetworkDisconnected()
{
    updateConnectionStatus(false);
    showMessage("连接断开");
    m_refreshTimer->stop();
}

void MainWindow::onNetworkError(const QString &msg)
{
    showMessage("网络错误: " + msg, true);
}

void MainWindow::updateConnectionStatus(bool connected)
{
    m_connectBtn->setProperty("connected", connected);
    m_connectBtn->style()->unpolish(m_connectBtn);
    m_connectBtn->style()->polish(m_connectBtn);

    if (connected) {
        m_statusLabel->setText("在线");
        m_statusLabel->setStyleSheet("color: #67c23a; font-weight: bold;");
        m_connectBtn->setText("断开连接");
        setControlsEnabled(true);
        statusBar()->showMessage("服务已连接", 3000);
    } else {
        m_statusLabel->setText("离线");
        m_statusLabel->setStyleSheet("color: #f56c6c; font-weight: bold;");
        m_connectBtn->setText("连接服务器");
        setControlsEnabled(false);
        m_statsLabel->setText("系统概览: 等待连接...");
        m_roomCombo->clear();
        statusBar()->showMessage("服务已断开", 3000);
    }
}

void MainWindow::showMessage(const QString &msg, bool isError)
{
    if (isError) {
        QMessageBox::critical(this, "错误", msg);
        statusBar()->showMessage("错误: " + msg, 5000);
    } else {
        // 普通消息改用状态栏显示，避免过多弹窗影响操作逻辑
        statusBar()->showMessage(msg, 5000);
    }
}

void MainWindow::onReadCardClicked()
{
    if (!m_network->isConnected()) {
        showMessage("请先连接服务器", true);
        return;
    }
    m_readCardBtn->setEnabled(false);
    m_readCardBtn->setText("读卡中...");
    m_pendingOp = PendingReadCard;
    m_network->readCard();
}

void MainWindow::onAddCardClicked()
{
    if (!m_network->isConnected()) {
        showMessage("请先连接服务器", true);
        return;
    }
    QString uid = m_uidEdit->text().trimmed();
    if (uid.isEmpty()) {
        showMessage("请输入卡号", true);
        return;
    }
    const QVariant roomIdData = m_roomCombo->currentData();
    if (!roomIdData.isValid()) {
        showMessage("请选择房间", true);
        return;
    }
    QString roomId = QString::number(roomIdData.toInt());
    QString expireDate = m_expireDateEdit->date().toString("yyyy-MM-dd");
    m_pendingOp = PendingAddCard;
    m_network->addCard(uid, roomId, expireDate, m_username);
}

void MainWindow::onOpenDoorClicked()
{
    if (!m_network->isConnected()) {
        showMessage("请先连接服务器", true);
        return;
    }
    if (!m_cardSelected) {
        showMessage("请先在列表中选中一张卡片", true);
        return;
    }
    QString uid = m_uidEdit->text().trimmed();
    if (uid.isEmpty()) {
        showMessage("请选择或输入卡号", true);
        return;
    }
    int ret = QMessageBox::question(this, "确认", "确定要开门吗?",
                                    QMessageBox::Yes | QMessageBox::No);
    if (ret != QMessageBox::Yes)
        return;
    m_pendingOp = PendingOpenDoor;
    m_pendingUid = uid;
    m_network->openDoor(uid);
}

void MainWindow::onCheckCardClicked()
{
    if (!m_network->isConnected()) {
        showMessage("请先连接服务器", true);
        return;
    }
    if (!m_cardSelected) {
        showMessage("请先在列表中选中一张卡片", true);
        return;
    }
    QString uid = m_uidEdit->text().trimmed();
    if (uid.isEmpty()) {
        showMessage("请选择或输入卡号", true);
        return;
    }
    m_pendingOp = PendingCheckCard;
    m_pendingUid = uid;
    m_network->checkCard(uid);
}

void MainWindow::onLostCardClicked()
{
    if (!m_network->isConnected()) {
        showMessage("请先连接服务器", true);
        return;
    }
    if (!m_cardSelected) {
        showMessage("请先在列表中选中一张卡片", true);
        return;
    }
    QString uid = m_uidEdit->text().trimmed();
    if (uid.isEmpty()) {
        showMessage("请选择或输入卡号", true);
        return;
    }
    m_pendingOp = PendingCheckCardForLost;
    m_pendingUid = uid;
    m_network->checkCard(uid);
}

void MainWindow::onCancelCardClicked()
{
    if (!m_network->isConnected()) {
        showMessage("请先连接服务器", true);
        return;
    }
    if (!m_cardSelected) {
        showMessage("请先在列表中选中一张卡片", true);
        return;
    }
    QString uid = m_uidEdit->text().trimmed();
    if (uid.isEmpty()) {
        showMessage("请选择或输入卡号", true);
        return;
    }
    m_pendingOp = PendingCheckCardForCancel;
    m_pendingUid = uid;
    m_network->checkCard(uid);
}

void MainWindow::onDeleteCardClicked()
{
    if (!m_network->isConnected()) {
        showMessage("请先连接服务器", true);
        return;
    }
    if (!m_cardSelected) {
        showMessage("请先在列表中选中一张卡片", true);
        return;
    }
    QString uid = m_uidEdit->text().trimmed();
    if (uid.isEmpty()) {
        showMessage("请选择或输入卡号", true);
        return;
    }
    int ret = QMessageBox::question(this, "确认",
                                    "确定要删除这张房卡吗?\n删除后将从数据库移除，无法恢复!",
                                    QMessageBox::Yes | QMessageBox::No);
    if (ret != QMessageBox::Yes)
        return;
    m_pendingOp = PendingDeleteCard;
    m_pendingUid = uid;
    m_network->deleteCard(uid, m_username);
}

void MainWindow::onRefreshClicked()
{
    if (!m_network->isConnected())
        return;
    m_refreshPreviousRoomId = m_roomCombo->currentData();
    m_inRefreshChain = true;
    m_pendingOp = PendingGetRooms;
    m_network->getRooms();
}

void MainWindow::setPendingRoomClick(const QString &roomName)
{
    m_pendingRoomNameForClick = roomName;
}

void MainWindow::requestCardsForRoomClick()
{
    m_pendingOp = PendingGetCardsForRoomClick;
    m_network->getCards();
}

void MainWindow::onCardTableClicked(int row, int column)
{
    Q_UNUSED(column)
    QTableWidgetItem *uidItem = m_cardTable->item(row, 0);
    if (uidItem) {
        m_uidEdit->setText(uidItem->text());
        m_cardSelected = true;  // 标记已选中卡片
    }

    QTableWidgetItem *roomIdItem = m_cardTable->item(row, 1);
    if (roomIdItem) {
        bool ok = false;
        const int roomId = roomIdItem->text().toInt(&ok);
        if (ok) {
            const int index = m_roomCombo->findData(roomId);
            if (index >= 0) {
                m_roomCombo->setCurrentIndex(index);
            }
        }
    }

    QTableWidgetItem *expireItem = m_cardTable->item(row, 4);
    if (expireItem) {
        const QDate expireDate = QDate::fromString(expireItem->text(), "yyyy-MM-dd");
        if (expireDate.isValid()) {
            m_expireDateEdit->setDate(expireDate);
        }
    }
}

void MainWindow::onResponseReady(const QString &response)
{
    QJsonParseError parseError;
    QJsonDocument doc = QJsonDocument::fromJson(response.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        if (m_pendingOp != PendingNone)
            showMessage("响应解析失败: " + parseError.errorString(), true);
        m_pendingOp = PendingNone;
        return;
    }
    QJsonObject obj = doc.object();
    const int code = obj["code"].toInt();

    switch (m_pendingOp) {
    case PendingReadCard: {
        m_pendingOp = PendingNone;
        m_readCardBtn->setEnabled(true);
        m_readCardBtn->setText("读卡");
        if (code == 200) {
            QString uid = obj["data"].toObject()["uid"].toString();
            m_uidEdit->setText(uid);
            QMessageBox::information(this, "读卡成功", QString("感应到 RFID 标签\n卡片ID: %1").arg(uid));
            showMessage("读卡成功: " + uid);
            addLiveEvent("感应到 RFID 标签, UID: " + uid);
        } else {
            showMessage(obj["msg"].toString(), true);
            addLiveEvent("读卡异常: " + obj["msg"].toString(), true);
        }
        break;
    }
    case PendingAddCard: {
        m_pendingOp = PendingNone;
        if (code == 200) {
            showMessage("发卡成功");
            addLiveEvent(QString("业务办理: 房间 %1 完成发卡 (UID: %2)").arg(m_roomCombo->currentText(), m_uidEdit->text().trimmed()));
            m_uidEdit->clear();
            refreshRoomList();
        } else {
            showMessage(obj["msg"].toString(), true);
            addLiveEvent("发卡失败: " + obj["msg"].toString(), true);
        }
        break;
    }
    case PendingOpenDoor: {
        m_pendingOp = PendingNone;
        if (code == 200 || code == 202) {
            showMessage(obj["msg"].toString());
            addLiveEvent("远程控制: 已下发开门任务，未确认舵机完成 (UID: " + m_pendingUid + ")");
        } else {
            showMessage(obj["msg"].toString(), true);
            addLiveEvent("开门失败: " + obj["msg"].toString(), true);
        }
        refreshRoomList();
        break;
    }
    case PendingCheckCard: {
        m_pendingOp = PendingNone;
        if (code == 200) {
            QJsonObject data = obj["data"].toObject();
            int status = data["status"].toInt();
            QString statusText = status == 0 ? "正常" : (status == 1 ? "挂失" : "注销");
            QString roomIdText;
            QJsonValue rv = data.value("room_id");
            if (rv.isDouble()) roomIdText = QString::number(rv.toInt());
            else if (rv.isString()) roomIdText = rv.toString();
            QString detail = QString("卡号: %1\n状态: %2\n房间ID: %3\n有效期: %4")
                .arg(m_pendingUid).arg(statusText).arg(roomIdText.isEmpty() ? "-" : roomIdText)
                .arg(data["expire_date"].toString().isEmpty() ? "-" : data["expire_date"].toString());
            QMessageBox::information(this, "房卡状态查询", detail);
            addLiveEvent("状态查询: UID " + m_pendingUid + " -> " + statusText);
        } else {
            showMessage(obj["msg"].toString(), true);
            addLiveEvent("状态查询失败: " + obj["msg"].toString(), true);
        }
        break;
    }
    case PendingCheckCardForLost: {
        m_pendingOp = PendingNone;
        if (code != 200) break;
        int st = obj["data"].toObject()["status"].toInt();
        if (st == 2) {
            QMessageBox::warning(this, "业务错误", "该房卡已经处于注销状态，无法执行挂失操作。\n(提示：注销等级高于挂失)");
            break;
        }
        if (st == 1) {
            QMessageBox::warning(this, "业务提醒", "该房卡当前已经是挂失状态，无需重复挂失。");
            break;
        }
        if (QMessageBox::question(this, "确认", "确定要挂失这张房卡吗?", QMessageBox::Yes | QMessageBox::No) != QMessageBox::Yes)
            break;
        m_pendingOp = PendingLostCard;
        m_network->lostCard(m_pendingUid, m_username);
        return;
    }
    case PendingLostCard: {
        m_pendingOp = PendingNone;
        if (code == 200) {
            showMessage("挂失成功");
            addLiveEvent("业务办理: 挂失卡片 (UID: " + m_pendingUid + ")");
            onRefreshClicked();
        } else {
            showMessage(obj["msg"].toString(), true);
            addLiveEvent("挂失卡片失败: " + obj["msg"].toString(), true);
        }
        break;
    }
    case PendingCheckCardForCancel: {
        m_pendingOp = PendingNone;
        if (code == 200 && obj["data"].toObject()["status"].toInt() == 2) {
            QMessageBox::warning(this, "业务提醒", "该房卡当前已经处于注销状态，无需重复注销。");
            break;
        }
        if (QMessageBox::question(this, "确认", "确定要注销这张房卡吗? 注销后无法恢复!", QMessageBox::Yes | QMessageBox::No) != QMessageBox::Yes)
            break;
        m_pendingOp = PendingCancelCard;
        m_network->cancelCard(m_pendingUid, m_username);
        return;
    }
    case PendingCancelCard: {
        m_pendingOp = PendingNone;
        if (code == 200) {
            showMessage("注销成功");
            addLiveEvent("业务办理: 注销退房 (UID: " + m_pendingUid + ")");
            onRefreshClicked();
        } else {
            showMessage(obj["msg"].toString(), true);
            addLiveEvent("注销失败: " + obj["msg"].toString(), true);
        }
        break;
    }
    case PendingDeleteCard: {
        m_pendingOp = PendingNone;
        if (code == 200) {
            showMessage("删除成功");
            addLiveEvent("记录管理: 物理删除房卡记录 (UID: " + m_pendingUid + ")");
            m_uidEdit->clear();
            refreshRoomList();
        } else {
            showMessage(obj["msg"].toString(), true);
            addLiveEvent("删除失败: " + obj["msg"].toString(), true);
        }
        break;
    }
    case PendingGetRooms: {
        if (code != 200) {
            m_inRefreshChain = false;
            showMessage(obj["msg"].toString(), true);
            m_pendingOp = PendingNone;
            break;
        }
        applyRoomsFromJson(obj["data"].toArray(), m_refreshPreviousRoomId);
        m_pendingOp = PendingGetCards;
        m_network->getCards();
        return;
    }
    case PendingGetCards: {
        if (code == 200) {
            QJsonArray cards = obj["data"].toArray();
            QDate today = QDate::currentDate();
            QList<QJsonObject> validCards;
            for (const QJsonValue &v : cards) {
                QJsonObject card = v.toObject();
                QString expireDateStr = card["expire_date"].toString();
                if (!expireDateStr.isEmpty()) {
                    QDate expireDate = QDate::fromString(expireDateStr, "yyyy-MM-dd");
                    if (expireDate.isValid() && expireDate < today)
                        continue;
                }
                validCards.append(card);
            }
            m_cardTable->setRowCount(validCards.size());
            for (int i = 0; i < validCards.size(); ++i) {
                QJsonObject card = validCards[i];
                QString roomIdText;
                QJsonValue rv = card.value("room_id");
                if (rv.isDouble()) roomIdText = QString::number(rv.toInt());
                else if (rv.isString()) roomIdText = rv.toString();
                m_cardTable->setItem(i, 0, new QTableWidgetItem(card["uid"].toString()));
                m_cardTable->setItem(i, 1, new QTableWidgetItem(roomIdText));
                m_cardTable->setItem(i, 2, new QTableWidgetItem(card["room_number"].toString()));
                m_cardTable->setItem(i, 3, new QTableWidgetItem(card["status_text"].toString()));
                m_cardTable->setItem(i, 4, new QTableWidgetItem(card["expire_date"].toString()));
                m_cardTable->setItem(i, 5, new QTableWidgetItem(card["create_time"].toString()));
                m_cardTable->setItem(i, 6, new QTableWidgetItem(card["update_time"].toString()));
            }
        } else {
            showMessage(obj["msg"].toString(), true);
            if (m_inRefreshChain) m_inRefreshChain = false;
        }
        if (m_inRefreshChain) {
            m_pendingOp = PendingGetLogs;
            m_network->getLogs(50);
            return;
        }
        m_pendingOp = PendingNone;
        break;
    }
    case PendingGetLogs: {
        if (code == 200) {
            QJsonArray logs = obj["data"].toArray();
            m_logTable->setRowCount(logs.size());
            for (int i = 0; i < logs.size(); ++i) {
                QJsonObject log = logs[i].toObject();
                int logId = log["id"].toInt();
                if (i == 0 && logId > m_lastLogId && m_lastLogId != 0) {
                    addLiveEvent(QString("新动态: %1 (UID: %2) - %3")
                        .arg(log["operation"].toString(), log["card_uid"].toString(), log["detail"].toString()),
                        log["result"].toInt() == 0);
                }
                if (i == 0) m_lastLogId = qMax(m_lastLogId, logId);
                m_logTable->setItem(i, 0, new QTableWidgetItem(QString::number(logId)));
                m_logTable->setItem(i, 1, new QTableWidgetItem(log["create_time"].toString()));
                m_logTable->setItem(i, 2, new QTableWidgetItem(log["card_uid"].toString()));
                m_logTable->setItem(i, 3, new QTableWidgetItem(log["operation"].toString()));
                m_logTable->setItem(i, 4, new QTableWidgetItem(log["operator"].toString()));
                m_logTable->setItem(i, 5, new QTableWidgetItem(log["result"].toInt() == 1 ? "成功" : "失败"));
                m_logTable->setItem(i, 6, new QTableWidgetItem(log["detail"].toString()));
                if (log["result"].toInt() == 0) {
                    for (int j = 0; j < 7; ++j)
                        if (m_logTable->item(i, j)) m_logTable->item(i, j)->setForeground(QColor("#f56c6c"));
                }
            }
            if (m_lastLogId == 0 && logs.size() > 0)
                m_lastLogId = logs[0].toObject()["id"].toInt();
        } else {
            showMessage(obj["msg"].toString(), true);
            if (m_inRefreshChain) m_inRefreshChain = false;
        }
        if (m_inRefreshChain) {
            m_pendingOp = PendingGetStats;
            m_network->getStats();
            return;
        }
        m_pendingOp = PendingNone;
        break;
    }
    case PendingGetStats: {
        m_inRefreshChain = false;
        m_pendingOp = PendingNone;
        if (code == 200) {
            QJsonObject data = obj["data"].toObject();
            int totalCards = data["total_cards"].toInt(), normalCards = data["normal_cards"].toInt();
            int lostCards = data["lost_cards"].toInt(), todayOpens = data["today_opens"].toInt();
            m_statsLabel->setText(QString("系统状态概览:  总发卡量 %1  |  正常使用 %2  |  挂失异常 %3  |  今日开门任务 %4")
                .arg(totalCards).arg(normalCards).arg(lostCards).arg(todayOpens));
            m_analysisStats[0]->setText(QString::number(totalCards));
            m_analysisStats[1]->setText(QString::number(normalCards));
            m_analysisStats[2]->setText(QString::number(lostCards));
            m_analysisStats[3]->setText(QString::number(todayOpens));
            int busyRooms = data["busy_rooms"].toInt(), totalRooms = data["total_rooms"].toInt();
            QDateTime now = QDateTime::currentDateTime();
            if (totalRooms > 0 && (!m_lastAnalysisTime.isValid() || m_lastAnalysisTime.secsTo(now) >= 300)) {
                addLiveEvent(QString("房态分析: 当前入住率 %1% (已住%2/总%3)").arg(busyRooms * 100 / totalRooms).arg(busyRooms).arg(totalRooms));
                m_lastAnalysisTime = now;
            }
        } else {
            m_statsLabel->setText("统计: -");
        }
        break;
    }
    case PendingGetCardsForRoomClick: {
        m_pendingOp = PendingNone;
        if (code == 200) {
            QJsonArray cards = obj["data"].toArray();
            QDate today = QDate::currentDate();
            QString foundUid;
            for (const QJsonValue &c : cards) {
                QJsonObject o = c.toObject();
                if (o["room_number"].toString() == m_pendingRoomNameForClick && o["status"].toInt() != 2) {
                    QString expireDateStr = o["expire_date"].toString();
                    if (!expireDateStr.isEmpty()) {
                        QDate expireDate = QDate::fromString(expireDateStr, "yyyy-MM-dd");
                        if (expireDate.isValid() && expireDate < today)
                            continue;
                    }
                    foundUid = o["uid"].toString();
                    break;
                }
            }
            if (!foundUid.isEmpty()) {
                m_uidEdit->setText(foundUid);
                m_cardSelected = true;
                onCheckCardClicked();
            } else {
                QMessageBox::information(this, "房间状态", QString("房间 %1 当前为空闲状态，暂无绑定卡片。").arg(m_pendingRoomNameForClick));
            }
        }
        break;
    }
    default:
        m_pendingOp = PendingNone;
        break;
    }
}

void MainWindow::refreshCardList()
{
    if (!m_network->isConnected())
        return;
    m_pendingOp = PendingGetCards;
    m_network->getCards();
}

void MainWindow::refreshLogList()
{
    if (!m_network->isConnected())
        return;
    m_pendingOp = PendingGetLogs;
    m_network->getLogs(50);
}

void MainWindow::refreshRoomList()
{
    if (!m_network->isConnected())
        return;
    m_refreshPreviousRoomId = m_roomCombo->currentData();
    m_inRefreshChain = true;
    m_pendingOp = PendingGetRooms;
    m_network->getRooms();
}

void MainWindow::applyRoomsFromJson(const QJsonArray &rooms, const QVariant &previousRoomId)
{
    m_roomCombo->clear();
    m_roomCombo->addItem("请选择房间", QVariant());
    for (int i = 0; i < rooms.size(); ++i) {
        QJsonObject room = rooms[i].toObject();
        const int id = room["id"].toInt();
        const QString roomNumber = room["room_number"].toString();
        const int floor = room["floor"].toInt();
        const QString text = floor > 0 ? QString("%1 (楼层%2)").arg(roomNumber).arg(floor) : roomNumber;
        m_roomCombo->addItem(text, id);
    }
    if (previousRoomId.isValid()) {
        const int idx = m_roomCombo->findData(previousRoomId);
        if (idx >= 0) m_roomCombo->setCurrentIndex(idx);
    }
    QLayoutItem *child;
    while ((child = m_roomLayout->takeAt(0)) != nullptr) {
        if (child->widget()) delete child->widget();
        delete child;
    }
    QMap<int, QList<QJsonObject>> floorMap;
    for (int i = 0; i < rooms.size(); ++i) {
        QJsonObject room = rooms[i].toObject();
        int floor = room["floor"].toInt();
        floorMap[floor].append(room);
    }

    // 2. 获取所有楼层并按降序排序 (楼层高的排在前面/上面)
    QList<int> floors = floorMap.keys();
    std::sort(floors.begin(), floors.end(), std::greater<int>());

    int currentRow = 0;
    for (int floor : floors) {
        // 添加楼层标签
        QLabel *floorLabel = new QLabel(QString("楼层 %1").arg(floor));
        floorLabel->setStyleSheet("font-weight: bold; color: #909399;");
        m_roomLayout->addWidget(floorLabel, currentRow, 0);

        QList<QJsonObject> floorRooms = floorMap[floor];
        // 楼层内按房间号排序
        std::sort(floorRooms.begin(), floorRooms.end(), [](const QJsonObject &a, const QJsonObject &b){
            return a["room_number"].toString() < b["room_number"].toString();
        });

        for (int i = 0; i < floorRooms.size(); ++i) {
            QJsonObject room = floorRooms[i];
            QString roomNo = room["room_number"].toString();
            int status = room["status"].toInt(); // 0:空闲, 1:入住
            int cardStatus = room.contains("card_status") && !room["card_status"].isNull()
                             ? room["card_status"].toInt() : -1;

            // 状态文字映射
            QString statusText = "VACANT";
            if (status == 1) {
                if (cardStatus == 0) statusText = "OCCUPIED";
                else if (cardStatus == 1) statusText = "LOST CARD";
                else if (cardStatus == 2) statusText = "CANCELLED";
                else statusText = "OCCUPIED";
            }

            RoomLabel *card = new RoomLabel(roomNo, this, m_roomTab);

            // 颜色逻辑：空闲(Gray), 正常入住(Green), 挂失(Orange), 注销/异常(Red)
            QString startColor = "#909399", endColor = "#606266";
            if (status == 1) {
                if (cardStatus == 1) { // 挂失
                    startColor = "#e6a23c"; endColor = "#c68a2a";
                } else if (cardStatus == 2) { // 注销
                    startColor = "#f56c6c"; endColor = "#d34949";
                } else { // 正常入住
                    startColor = "#67c23a"; endColor = "#529b2e";
                }
            }

            // 使用简化的 QSS 语法，确保兼容性
            QString bgGradient = QString("qlineargradient(spread:pad, x1:0, y1:0, x2:0, y2:1, stop:0 %1, stop:1 %2)").arg(startColor, endColor);

            card->setStyleSheet(QString(
                "background-color: %1; "
                "color: white; "
                "font-weight: bold; "
                "border-radius: 10px; "
                "border: 1px solid rgba(255,255,255,0.3); "
                "padding: 5px;"
            ).arg(bgGradient));

            card->setFixedSize(110, 85);
            card->setAlignment(Qt::AlignCenter);

            // 房号与状态一起显示 (限制状态文字字号防止撑开)
            card->setText(QString("<div align='center'><span style='font-size:18px;'>%1</span><br><span style='font-size:10px;'>%2</span></div>")
                          .arg(roomNo).arg(statusText));

            // 从第一列之后开始放房间
            m_roomLayout->addWidget(card, currentRow, i + 1);
        }
        currentRow++;
    }
    m_roomLayout->setColumnStretch(99, 1); // 挤正布局
    addLiveEvent("同步房态地图成功 (楼层视图)");
}

void MainWindow::refreshStats()
{
    if (!m_network->isConnected()) {
        m_statsLabel->setText("统计: -");
        return;
    }
    m_pendingOp = PendingGetStats;
    m_network->getStats();
}

void MainWindow::setupCardTable()
{
    m_cardTable->setColumnCount(7);
    m_cardTable->setHorizontalHeaderLabels({"卡号 (UID)", "房间ID", "房间号", "状态", "过期时间", "创建时间", "最后更新"});
    m_cardTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    m_cardTable->horizontalHeader()->setSectionResizeMode(1, QHeaderView::ResizeToContents); // 房间ID短一点
    m_cardTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_cardTable->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_cardTable->setAlternatingRowColors(true);
    m_cardTable->verticalHeader()->setVisible(false); // 隐藏行号更显简洁
    m_cardTable->setShowGrid(false); // 配合 QSS 隐藏网格线
}

void MainWindow::setupLogTable()
{
    m_logTable->setColumnCount(7);
    m_logTable->setHorizontalHeaderLabels({"流水号", "操作时间", "卡号", "操作类型", "操作人", "结果", "详情"});
    m_logTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    m_logTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_logTable->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_logTable->setAlternatingRowColors(true);
    m_logTable->verticalHeader()->setVisible(false);
    m_logTable->setShowGrid(false);
}
