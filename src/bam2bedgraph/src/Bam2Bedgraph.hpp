/****************************************************************************
**
** Copyright (C) 2011 Andrey Kartashov .
** All rights reserved.
** Contact: Andrey Kartashov (porter@porter.st)
**
** This file is part of the global module of the genome-tools.
**
** GNU Lesser General Public License Usage
** This file may be used under the terms of the GNU Lesser General Public
** License version 2.1 as published by the Free Software Foundation and
** appearing in the file LICENSE.LGPL included in the packaging of this
** file. Please review the following information to ensure the GNU Lesser
** General Public License version 2.1 requirements will be met:
** http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
**
** Other Usage
** Alternatively, this file may be used in accordance with the terms and
** conditions contained in a signed written agreement between you and Andrey Kartashov.
**
****************************************************************************/
#ifndef _Bam2Bedgraph_
#define _Bam2Bedgraph_


#include <config.hpp>


#define FSTM Bam2Bedgraph


class Bam2Bedgraph: public QObject
{
    Q_OBJECT
private:


public slots:

    void start(void);

public:

    FSTM(QObject* parent=0);
    ~FSTM();
signals:
    void finished(void);

};

#endif
