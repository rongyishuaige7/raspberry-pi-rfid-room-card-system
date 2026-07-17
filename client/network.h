#ifndef NETWORK_H
#define NETWORK_H

#include <QObject>
#include <QTcpSocket>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>
#include <QHostAddress>
#include <QByteArray>

class Network : public QObject
{
    Q_OBJECT
public:
    explicit Network(QObject *parent = nullptr);
    ~Network();

    void connectToServer(const QString &host, quint16 port);
    void disconnect();
    bool isConnected() const;
    QString host() const { return m_host; }
    quint16 port() const { return m_port; }

    QString login(const QString &username, const QString &password);

    void setSessionToken(const QString &token);
    void clearSessionToken();

    // 同步发送（仅用于登录），返回响应 JSON 字符串
    QString sendCommand(const QString &cmd);

    // 异步发送：只写不阻塞，响应通过 responseReady 信号返回
    void sendCommandAsync(const QString &cmd);

    // 便捷方法（异步，结果通过 responseReady）
    void readCard();
    void openDoor(const QString &uid);
    void checkCard(const QString &uid);
    void getStats();
    void addCard(const QString &uid, const QString &roomId = "", const QString &expireDate = "", const QString &operatorName = "admin");
    void lostCard(const QString &uid, const QString &operatorName = "admin");
    void cancelCard(const QString &uid, const QString &operatorName = "admin");
    void deleteCard(const QString &uid, const QString &operatorName = "admin");
    void getLogs(int limit = 100);
    void getCards();
    void getRooms();

signals:
    void connected();
    void disconnected();
    void errorOccurred(const QString &msg);
    void responseReady(const QString &response);

private slots:
    void onConnected();
    void onDisconnected();
    void onSocketError(QAbstractSocket::SocketError error);
    void onReadyRead();

private:
    QTcpSocket *m_socket;
    QString m_host;
    quint16 m_port;
    QByteArray m_readBuffer;
    QString m_token;
    bool m_blockingSend = false;  // 为 true 时 onReadyRead 不发射 responseReady，供 sendCommand 同步读
};

#endif // NETWORK_H
