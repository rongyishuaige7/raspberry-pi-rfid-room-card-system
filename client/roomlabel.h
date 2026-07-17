#ifndef ROOMLABEL_H
#define ROOMLABEL_H

#include <QLabel>

class MainWindow;

class RoomLabel : public QLabel
{
    Q_OBJECT
public:
    explicit RoomLabel(const QString &roomName, MainWindow *mainWindow, QWidget *parent = nullptr);

protected:
    void mouseReleaseEvent(QMouseEvent *event) override;

private:
    QString m_roomName;
    MainWindow *m_mainWindow = nullptr;
};

#endif // ROOMLABEL_H
