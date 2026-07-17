#include "network.h"
#include <QDebug>
#include <QCryptographicHash>

Network::Network(QObject *parent)
    : QObject(parent)
    , m_socket(new QTcpSocket(this))
    , m_port(8888)
{
    connect(m_socket, &QTcpSocket::connected, this, &Network::onConnected);
    connect(m_socket, &QTcpSocket::disconnected, this, &Network::onDisconnected);
    connect(m_socket, &QAbstractSocket::errorOccurred, this, &Network::onSocketError);
    connect(m_socket, &QTcpSocket::readyRead, this, &Network::onReadyRead);
}

Network::~Network()
{
    if (m_socket->isOpen()) {
        m_socket->close();
    }
}

void Network::connectToServer(const QString &host, quint16 port)
{
    m_host = host;
    m_port = port;
    m_readBuffer.clear();
    m_socket->connectToHost(host, port);
    m_socket->waitForConnected(5000);
}

void Network::disconnect()
{
    m_readBuffer.clear();
    m_socket->disconnectFromHost();
}

bool Network::isConnected() const
{
    return m_socket->state() == QAbstractSocket::ConnectedState;
}

QString Network::login(const QString &username, const QString &password)
{
    // Historical protocol compatibility: this digest is replayable on plaintext TCP.
    // Use this prototype only on a trusted, isolated LAN.
    QByteArray hash = QCryptographicHash::hash(password.toUtf8(), QCryptographicHash::Sha256);
    QString hashHex = QString::fromLatin1(hash.toHex());
    return sendCommand(QString("LOGIN:%1:%2").arg(username).arg(hashHex));
}

void Network::setSessionToken(const QString &token)
{
    m_token = token;
}

void Network::clearSessionToken()
{
    m_token.clear();
}

QString Network::sendCommand(const QString &cmd)
{
    if (!isConnected()) {
        return QString("{\"code\":-1,\"msg\":\"未连接\"}");
    }

    QString out = cmd;
    if (!m_token.isEmpty() && !cmd.startsWith("LOGIN:")) {
        int idx = cmd.indexOf(':');
        if (idx < 0)
            out = cmd + ":" + m_token;
        else
            out = cmd.left(idx + 1) + m_token + ":" + cmd.mid(idx + 1);
    }

    QByteArray payload = out.toUtf8();
    if (!payload.endsWith('\n'))
        payload.append('\n');

    const qint64 written = m_socket->write(payload);
    if (written < 0)
        return QString("{\"code\":-3,\"msg\":\"发送失败\"}");
    if (!m_socket->waitForBytesWritten(2000))
        return QString("{\"code\":-3,\"msg\":\"发送超时\"}");

    m_blockingSend = true;
    const int timeoutMs = 10000;
    while (true) {
        const int newlineIndex = m_readBuffer.indexOf('\n');
        if (newlineIndex >= 0) {
            QByteArray line = m_readBuffer.left(newlineIndex);
            m_readBuffer.remove(0, newlineIndex + 1);
            if (line.endsWith('\r'))
                line.chop(1);
            m_blockingSend = false;
            return QString::fromUtf8(line);
        }
        if (!m_socket->waitForReadyRead(timeoutMs)) {
            m_blockingSend = false;
            return QString("{\"code\":-2,\"msg\":\"超时\"}");
        }
        m_readBuffer += m_socket->readAll();
    }
}

void Network::sendCommandAsync(const QString &cmd)
{
    if (!isConnected()) {
        emit responseReady(QString("{\"code\":-1,\"msg\":\"未连接\"}"));
        return;
    }
    QString out = cmd;
    if (!m_token.isEmpty() && !cmd.startsWith("LOGIN:")) {
        int idx = cmd.indexOf(':');
        if (idx < 0)
            out = cmd + ":" + m_token;
        else
            out = cmd.left(idx + 1) + m_token + ":" + cmd.mid(idx + 1);
    }
    QByteArray payload = out.toUtf8();
    if (!payload.endsWith('\n'))
        payload.append('\n');
    m_socket->write(payload);
}

void Network::onReadyRead()
{
    m_readBuffer += m_socket->readAll();
    if (m_blockingSend)
        return;  // 同步 sendCommand 会自己从 m_readBuffer 取行
    while (true) {
        const int newlineIndex = m_readBuffer.indexOf('\n');
        if (newlineIndex < 0)
            break;
        QByteArray line = m_readBuffer.left(newlineIndex);
        m_readBuffer.remove(0, newlineIndex + 1);
        if (line.endsWith('\r'))
            line.chop(1);
        emit responseReady(QString::fromUtf8(line));
    }
}

void Network::readCard()
{
    sendCommandAsync("READ_CARD");
}

void Network::openDoor(const QString &uid)
{
    sendCommandAsync(QString("OPEN_DOOR:%1").arg(uid));
}

void Network::checkCard(const QString &uid)
{
    sendCommandAsync(QString("CHECK_CARD:%1").arg(uid));
}

void Network::getStats()
{
    sendCommandAsync("GET_STATS");
}

void Network::addCard(const QString &uid, const QString &roomId, const QString &expireDate, const QString &operatorName)
{
    sendCommandAsync(QString("ADD_CARD:%1:%2:%3:%4").arg(uid).arg(roomId).arg(expireDate).arg(operatorName));
}

void Network::lostCard(const QString &uid, const QString &operatorName)
{
    sendCommandAsync(QString("LOST_CARD:%1:%2").arg(uid).arg(operatorName));
}

void Network::cancelCard(const QString &uid, const QString &operatorName)
{
    sendCommandAsync(QString("CANCEL_CARD:%1:%2").arg(uid).arg(operatorName));
}

void Network::deleteCard(const QString &uid, const QString &operatorName)
{
    sendCommandAsync(QString("DELETE_CARD:%1:%2").arg(uid).arg(operatorName));
}

void Network::getLogs(int limit)
{
    sendCommandAsync(QString("GET_LOGS:%1").arg(limit));
}

void Network::getCards()
{
    sendCommandAsync("GET_CARDS");
}

void Network::getRooms()
{
    sendCommandAsync("GET_ROOMS");
}

void Network::onConnected()
{
    qDebug() << "已连接服务器";
    m_readBuffer.clear();
    emit connected();
}

void Network::onDisconnected()
{
    qDebug() << "已断开连接";
    m_readBuffer.clear();
    // 不断开时清除 token，重连后仍可沿用当前登录态，避免提示「未登录/会话已失效」
    emit disconnected();
}

void Network::onSocketError(QAbstractSocket::SocketError error)
{
    Q_UNUSED(error);
    QString msg = m_socket->errorString();
    qDebug() << "网络错误:" << msg;
    emit errorOccurred(msg);
}
