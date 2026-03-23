export const neck = {
    name: 'neck',
    title: 'Повороты шеи',
    defaultReps: 10,
    
    instructions: [
        { 
            text: 'Сядьте или встаньте прямо, расслабьте плечи',
            svg: `<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="5" r="3" fill="#4CAF50"/>
                <path d="M12 8 L12 14" stroke="#4CAF50"/>
                <path d="M12 14 L9 20" stroke="#4CAF50"/>
                <path d="M12 14 L15 20" stroke="#4CAF50"/>
                <path d="M12 10 L8 13" stroke="#4CAF50"/>
                <path d="M12 10 L16 13" stroke="#4CAF50"/>
            </svg>`
        },
        { 
            text: 'Медленно поверните голову ВЛЕВО до упора',
            svg: `<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#FF5722" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 12H5"/>
                <path d="M5 12l6 6"/>
                <path d="M5 12l6-6"/>
            </svg>`
        },
        { 
            text: 'Плавно вернитесь в центральное положение',
            svg: `<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#4CAF50" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9"/>
                <circle cx="12" cy="12" r="3" fill="#4CAF50"/>
            </svg>`
        },
        { 
            text: 'Медленно поверните голову ВПРАВО до упора',
            svg: `<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#2196F3" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 12h14"/>
                <path d="M19 12l-6 6"/>
                <path d="M19 12l-6-6"/>
            </svg>`
        },
        { 
            text: 'Вернитесь в центр - это 1 повторение',
            svg: `<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#FFD700" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
            </svg>`
        }
    ],
    
    svgIcons: {
        // Стрелка влево из Material Design
        headLeft: `<svg width="120" height="120" viewBox="0 0 24 24" fill="none">
            ircle cx="12" cy="12" r="11" fill="#FF5722" opacity="0.9595"/>
            <path d="M15 18l-6-6 6-6" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`,
        
        // Стрелка вправо из Material Design
        headRight: `<svg width="120" height="120" viewBox="0 0 24 24" fill="none">
            ircle cx="12" cy="12" r="11" fill="#2#2196F3" opacity="0.95"/>
            <path d="M9 18l6-6-6-6" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`,
        
        // Центр из Material Design
        headCenter: `<svg width="120" height="120" viewBox="0 0 24 24" fill="none">
            ircle cx="12" cy="12" r="11" fill="#4CAF50"0" opacity="0.95"/>
            ircle cx="12" cy="12"2" r="3" fill="white"/>
            ircle cx="12" cy="12" r="6" stroke="white" stroke-width="2"2" fill="none"/>
        </svg>`,
        
        // Галочка из Material Design
        check: `<svg width="120" height="120" viewBox="0 0 24 24" fill="none">
            ircle cx="12" cy="12"2" r="11" fill="#4CAF50"/>
            <polyline points="7 12 10 15 17 8" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`,
        
        // Предупреждение из Material Design
        warning: `<svg width="120" height="120" viewBox="0 0 24 24" fill="none">
            ircle cx="12" cy="12" r="11"1" fill="#FF9800"/>
            <line x1="12" y1="7" x2="12" y2="13" stroke="white" stroke-width="3" stroke-linecap="round"/>
            ircle cx="12" cy="1616" r="1" fill="white"/>
        </svg>`
    },
    
    thresholds: {
        leftOffset: 0.08,
        rightOffset: -0.08,
        centerTolerance: 0.04,
        partialLeft: 0.05,
        partialRight: -0.05,
        maxTime: 2000,
        minTime: 500
    },
    
    getInitialState() {
        return { 
            cycle: 'none',
            startTime: 0,
            lastStateTime: 0
        };
    },
    
    analyze(lm, state, showHint, logError, calcAngle) {
        const nose = lm[1], leftCheek = lm[234], rightCheek = lm[454];
        const center = (leftCheek.x + rightCheek.x) / 2;
        const offset = nose.x - center;
        const now = performance.now();
        
        let result = { counted: false, correct: false, status: 'Поверните влево' };
        
        if (state.cycle === 'none' || state.cycle === 'complete') {
            state.startTime = now;
            state.lastStateTime = now;
            
            if (offset > this.thresholds.leftOffset) {
                state.cycle = 'left';
                state.lastStateTime = now;
                showHint('Отлично! Верните в центр', this.svgIcons.headCenter, 'rgba(76, 175, 80, 0.95)', 4000);
                result.status = 'Влево выполнено';
            } else if (offset > this.thresholds.partialLeft) {
                showHint('Поворачивайте СИЛЬНЕЕ влево!', this.svgIcons.headLeft, 'rgba(255, 87, 34, 0.95)', 2500);
                result.status = 'Поворачивайте сильнее';
            } else {
                showHint('Поверните голову ВЛЕВО', this.svgIcons.headLeft, 'rgba(255, 87, 34, 0.95)', 3000);
                result.status = 'Поверните влево';
            }
        } 
        else if (state.cycle === 'left') {
            const timeSinceLastState = now - state.lastStateTime;
            
            if (Math.abs(offset) < this.thresholds.centerTolerance) {
                if (timeSinceLastState < this.thresholds.minTime) {
                    showHint('Двигайтесь МЕДЛЕННЕЕ!', this.svgIcons.warning, 'rgba(255, 152, 0, 0.95)', 3000);
                    logError('Слишком быстрое движение');
                }
                state.cycle = 'center_after_left';
                state.lastStateTime = now;
                showHint('Отлично! Теперь ВПРАВО', this.svgIcons.headRight, 'rgba(33, 150, 243, 0.95)', 4000);
                result.status = 'Теперь вправо';
            } else if (offset < 0) {
                showHint('Сначала в ЦЕНТР!', this.svgIcons.headCenter, 'rgba(244, 67, 54, 0.95)', 2500);
                logError('Пропущен центр');
                state.cycle = 'center_after_left';
            } else {
                result.status = 'Возвращайтесь в центр';
            }
        } 
        else if (state.cycle === 'center_after_left') {
            if (offset < this.thresholds.rightOffset) {
                state.cycle = 'right';
                state.lastStateTime = now;
                showHint('Отлично! Верните в центр', this.svgIcons.headCenter, 'rgba(76, 175, 80, 0.95)', 4000);
                result.status = 'Вправо выполнено';
            } else if (offset < this.thresholds.partialRight) {
                showHint('Поворачивайте СИЛЬНЕЕ вправо!', this.svgIcons.headRight, 'rgba(33, 150, 243, 0.95)', 2500);
                result.status = 'Поворачивайте сильнее';
            } else {
                showHint('Поверните голову ВПРАВО', this.svgIcons.headRight, 'rgba(33, 150, 243, 0.95)', 3000);
                result.status = 'Поверните вправо';
            }
        } 
        else if (state.cycle === 'right') {
            const timeSinceLastState = now - state.lastStateTime;
            
            if (Math.abs(offset) < this.thresholds.centerTolerance) {
                const totalTime = now - state.startTime;
                state.cycle = 'complete';
                result.counted = true;
                
                if (timeSinceLastState < this.thresholds.minTime) {
                    showHint('Двигайтесь МЕДЛЕННЕЕ!', this.svgIcons.warning, 'rgba(255, 152, 0, 0.95)', 3000);
                    logError('Слишком быстро');
                    result.correct = false;
                } else if (totalTime < this.thresholds.minTime * 4) {
                    showHint('Выполняйте МЕДЛЕННЕЕ!', this.svgIcons.warning, 'rgba(255, 152, 0, 0.95)', 3000);
                    logError('Быстрый цикл');
                    result.correct = false;
                } else {
                    showHint('ПОВТОРЕНИЕ ЗАВЕРШЕНО!', this.svgIcons.check, 'rgba(76, 175, 80, 0.95)', 5000);
                    result.correct = true;
                }
                result.status = 'Завершено';
            } else if (offset > 0) {
                showHint('Сначала в ЦЕНТР!', this.svgIcons.headCenter, 'rgba(244, 67, 54, 0.95)', 2500);
                logError('Пропущен центр');
                state.cycle = 'complete';
                result.counted = true;
                result.correct = false;
            } else {
                result.status = 'Возвращайтесь в центр';
            }
        }
        
        return result;
    }
};
