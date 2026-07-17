#ifndef LOGINDIALOG_H
#define LOGINDIALOG_H

#include <QDialog>
#include <QLineEdit>
#include <QComboBox>
#include <QPushButton>
#include <QLabel>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include "network.h"

class LoginDialog : public QDialog
{
    Q_OBJECT

public:
    explicit LoginDialog(Network *network, QWidget *parent = nullptr);
    struct User {
        QString username;
        QString role; // Admin, FrontDesk, Housekeeping
    };
    User getLoggedInUser() { return m_user; }

private slots:
    void onLoginClicked();

private:
    QLineEdit *m_usernameEdit;
    QLineEdit *m_passwordEdit;
    QComboBox *m_roleCombo;
    User m_user;
    Network *m_network;

    void setupUI();
};

#endif // LOGINDIALOG_H
