#include "roomlabel.h"
#include "mainwindow.h"
#include <QMouseEvent>
#include <QMessageBox>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>

RoomLabel::RoomLabel(const QString &roomName, MainWindow *mainWindow, QWidget *parent)
    : QLabel(parent)
    , m_roomName(roomName)
    , m_mainWindow(mainWindow)
{
    setCursor(Qt::PointingHandCursor);
}

void RoomLabel::mouseReleaseEvent(QMouseEvent *event)
{
    QLabel::mouseReleaseEvent(event);
    if (!m_mainWindow || !m_mainWindow->network())
        return;
    m_mainWindow->setPendingRoomClick(m_roomName);
    m_mainWindow->requestCardsForRoomClick();
}
