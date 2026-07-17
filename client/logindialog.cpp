#include "logindialog.h"
#include <QMessageBox>
#include <QStyle>
#include <QApplication>

LoginDialog::LoginDialog(Network *network, QWidget *parent)
    : QDialog(parent)
    , m_network(network)
{
    setupUI();
}

void LoginDialog::setupUI()
{
    setWindowTitle("登录 - 房卡管理系统");
    setFixedSize(400, 480);
    setWindowFlags(windowFlags() & ~Qt::WindowContextHelpButtonHint); // 移除问号

    // 全局 QSS
    QString qss =
        "QDialog { background-color: #f5f7fa; }"
        "QLineEdit { border: 1px solid #dcdfe6; border-radius: 6px; padding: 10px 15px; background: white; font-size: 14px; }"
        "QLineEdit:focus { border-color: #409eff; background: #ffffff; }"
        "QPushButton#loginBtn { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #409eff, stop:1 #66b1ff); color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 16px; }"
        "QPushButton#loginBtn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #66b1ff, stop:1 #85ce61); }"
        "QPushButton#loginBtn:pressed { background: #3a8ee6; }"
        "QLabel#tipLabel { color: #909399; font-size: 12px; }"
    ;
    this->setStyleSheet(qss);

    QVBoxLayout *mainLayout = new QVBoxLayout(this);
    mainLayout->setSpacing(25);
    mainLayout->setContentsMargins(50, 40, 50, 40);

    // 顶部 Logo/标题区
    QWidget *header = new QWidget(this);
    QVBoxLayout *headerLayout = new QVBoxLayout(header);
    headerLayout->setContentsMargins(0, 0, 0, 0);
    headerLayout->setSpacing(5);

    QLabel *titleLabel = new QLabel("SMART CARD", this);
    titleLabel->setAlignment(Qt::AlignCenter);
    titleLabel->setStyleSheet("font-size: 28px; font-weight: 800; color: #409eff; font-family: 'Arial Black';");
    headerLayout->addWidget(titleLabel);

    QLabel *subTitle = new QLabel("房卡管理平台", this);
    subTitle->setAlignment(Qt::AlignCenter);
    subTitle->setStyleSheet("font-size: 14px; color: #606266; font-weight: 500; letter-spacing: 2px;");
    headerLayout->addWidget(subTitle);

    mainLayout->addWidget(header);

    // 输入区
    QVBoxLayout *inputLayout = new QVBoxLayout();
    inputLayout->setSpacing(15);

    m_usernameEdit = new QLineEdit(this);
    m_usernameEdit->setPlaceholderText("请输入工号/用户名");
    m_usernameEdit->setFixedHeight(45);
    inputLayout->addWidget(m_usernameEdit);

    m_passwordEdit = new QLineEdit(this);
    m_passwordEdit->setPlaceholderText("请输入密码");
    m_passwordEdit->setEchoMode(QLineEdit::Password);
    m_passwordEdit->setFixedHeight(45);
    inputLayout->addWidget(m_passwordEdit);

    mainLayout->addLayout(inputLayout);

    // 登录按钮
    QPushButton *loginBtn = new QPushButton("登录", this);
    loginBtn->setObjectName("loginBtn");
    loginBtn->setFixedHeight(50);
    loginBtn->setCursor(Qt::PointingHandCursor);
    mainLayout->addWidget(loginBtn);

    // 底部提示
    QLabel *tipLabel = new QLabel(this);
    tipLabel->setObjectName("tipLabel");
    tipLabel->setText("Rongyi · Educational prototype");
    tipLabel->setAlignment(Qt::AlignCenter);
    mainLayout->addWidget(tipLabel);

    connect(loginBtn, &QPushButton::clicked, this, &LoginDialog::onLoginClicked);
}

void LoginDialog::onLoginClicked()
{
    QString username = m_usernameEdit->text();
    QString password = m_passwordEdit->text();

    if (username.isEmpty() || password.isEmpty()) {
        QMessageBox::warning(this, "登录", "请输入用户名和密码");
        return;
    }

    if (!m_network || !m_network->isConnected()) {
        QMessageBox::critical(this, "错误", "未连接到服务器，请先确保网络正常");
        return;
    }

    QString response = m_network->login(username, password);
    QJsonDocument doc = QJsonDocument::fromJson(response.toUtf8());
    QJsonObject obj = doc.object();

    if (obj["code"].toInt() == 200) {
        QJsonObject data = obj["data"].toObject();
        m_user.username = data["username"].toString();
        m_user.role = data["role"].toString();
        QString token = data["token"].toString();
        if (!token.isEmpty())
            m_network->setSessionToken(token);
        accept();
    } else {
        QString msg = obj["msg"].toString();
        if (msg.isEmpty()) msg = "账号或密码错误";
        QMessageBox::warning(this, "登录失败", msg);
    }
}
