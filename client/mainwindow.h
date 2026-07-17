#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QTableWidget>
#include <QLineEdit>
#include <QPushButton>
#include <QLabel>
#include <QComboBox>
#include <QDateEdit>
#include <QTimer>
#include <QGridLayout>
#include <QListWidget>
#include <QGroupBox>
#include <QVariant>
#include "network.h"

QT_BEGIN_NAMESPACE
namespace Ui { class MainWindow; }
QT_END_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

    void setUserRole(const QString &role, const QString &username);
    void setNetwork(Network *net);
    Network *network() const { return m_network; }
    void setPendingRoomClick(const QString &roomName);
    void requestCardsForRoomClick();

signals:
    void logoutRequested();

private slots:
    // 连接相关
    void onConnectClicked();
    void onNetworkConnected();
    void onNetworkDisconnected();
    void onNetworkError(const QString &msg);

    // 房卡操作
    void onReadCardClicked();
    void onAddCardClicked();
    void onOpenDoorClicked();
    void onCheckCardClicked();
    void onLostCardClicked();
    void onCancelCardClicked();
    void onDeleteCardClicked();
    void onRefreshClicked();
    void onExportClicked();
    void onLogoutClicked();
    void onSearchTextChanged(const QString &text);

    // 表格操作
    void onCardTableClicked(int row, int column);

    void onResponseReady(const QString &response);

private:
    enum PendingOp {
        PendingNone,
        PendingReadCard,
        PendingAddCard,
        PendingOpenDoor,
        PendingCheckCard,
        PendingLostCard,
        PendingCancelCard,
        PendingDeleteCard,
        PendingGetCards,
        PendingGetLogs,
        PendingGetRooms,
        PendingGetStats,
        PendingCheckCardForLost,
        PendingCheckCardForCancel,
        PendingGetCardsForRoomClick
    };
    void setupUI();
    void setupCardTable();
    void setupLogTable();
    void setControlsEnabled(bool enabled);
    void updateConnectionStatus(bool connected);
    void showMessage(const QString &msg, bool isError = false);
    void refreshCardList();
    void refreshLogList();
    void refreshRoomList();
    void refreshStats();
    void applyRoomsFromJson(const QJsonArray &rooms, const QVariant &previousRoomId);

private:
    Ui::MainWindow *ui;
    Network *m_network;

    // 连接相关
    QLineEdit *m_hostEdit;
    QLineEdit *m_portEdit;
    QPushButton *m_connectBtn;
    QPushButton *m_logoutBtn;
    QLabel *m_statusLabel;

    // 房卡管理
    QTableWidget *m_cardTable;
    QLineEdit *m_uidEdit;
    QComboBox *m_roomCombo;
    QDateEdit *m_expireDateEdit;
    QPushButton *m_readCardBtn;
    QPushButton *m_addCardBtn;
    QPushButton *m_openDoorBtn;
    QPushButton *m_checkCardBtn;
    QPushButton *m_lostCardBtn;
    QPushButton *m_cancelCardBtn;
    QPushButton *m_deleteCardBtn;
    QPushButton *m_refreshBtn;
    QLineEdit *m_searchEdit;
    QLabel *m_statsLabel;

    // 日志与分析
    QTableWidget *m_logTable;
    QWidget *m_analysisTab;
    QPushButton *m_exportBtn;
    QLabel *m_userLabel;
    QTabWidget *m_tabWidget;
    QLabel *m_analysisStats[4]; // 总卡数, 正常卡数, 挂失卡数, 今日开门

    // 房间地图
    QWidget *m_roomTab;
    QGridLayout *m_roomLayout;

    // 实时监控
    QGroupBox *m_monitorGroup;
    QListWidget *m_liveMonitor;
    void addLiveEvent(const QString &text, bool critical = false);

    QString m_role;
    QString m_username;

    // 选中状态
    bool m_cardSelected;

    // 实时监控
    QTimer *m_refreshTimer;
    int m_lastLogId;
    QDateTime m_lastAnalysisTime;

    PendingOp m_pendingOp = PendingNone;
    QString m_pendingRoomNameForClick;
    QString m_pendingUid;
    QVariant m_refreshPreviousRoomId;
    bool m_inRefreshChain = false;
};

#endif // MAINWINDOW_H
