#include "mainwindow.h"
#include "logindialog.h"
#include <QApplication>
#include <QInputDialog>

int main(int argc, char *argv[])
{
    QApplication a(argc, argv);
    a.setApplicationName("房卡管理系统");
    a.setApplicationVersion("1.0.0");

    // 全局网络对象
    Network net;

    // 弹个简单的输入框输入服务器IP，或者先连固定的
    QString host = QInputDialog::getText(nullptr, "服务器设置", "请输入树莓派IP地址:", QLineEdit::Normal, "127.0.0.1");
    if (host.isEmpty()) return 0;
    net.connectToServer(host, 8888);

    bool keepRunning = true;
    while (keepRunning) {
        LoginDialog login(&net);
        if (login.exec() == QDialog::Accepted) {
            auto user = login.getLoggedInUser();
            MainWindow w;
            w.setNetwork(&net); // 将已连接的网络对象传入
            w.setUserRole(user.role, user.username);

            bool shouldLogout = false;
            QObject::connect(&w, &MainWindow::logoutRequested, [&]() {
                shouldLogout = true;
                net.clearSessionToken();
            });

            w.show();
            a.exec();

            if (!shouldLogout) {
                keepRunning = false;
            }
        } else {
            keepRunning = false;
        }
    }

    return 0;
}
