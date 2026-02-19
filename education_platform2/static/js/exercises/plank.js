export const plank = {
    name: 'plank',
    title: 'Планка',
    defaultReps: 60, // 60 секунд
    
    instructions: [
        'Примите упор на локтях и носках',
        'Локти строго под плечами',
        'Тело образует прямую линию',
        'Напрягите пресс и ягодицы',
        'Не опускайте и не поднимайте бедра',
        'Дышите ровно, держите позицию'
    ],
    
    svgIcons: {
        bodyStraight: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><rect x="20" y="28" width="24" height="4"/><circle cx="20" cy="30" r="3"/><circle cx="44" cy="30" r="3"/></svg>',
        hipsDown: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M20 25 L32 35 L44 25" stroke="white" stroke-width="3" fill="none"/><path d="M32 35 L32 40 M28 36 L32 40 L36 36" stroke="white" stroke-width="2" fill="none"/></svg>',
        hipsUp: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M20 35 L32 25 L44 35" stroke="white" stroke-width="3" fill="none"/><path d="M32 25 L32 20 M28 24 L32 20 L36 24" stroke="white" stroke-width="2" fill="none"/></svg>',
        warning: '<svg width="48" height="48" viewBox="0 0 24 24" fill="white"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>'
    },
    
    thresholds: {
        bodyAngleMin: 155,      // Минимальный угол тела
        bodyAngleMax: 205,      // Максимальный угол тела
        hipShoulderDiff: 0.12,  // Максимальная разница высоты бедер и плеч
        checkInterval: 10       // Проверка каждую секунду (10 * 0.1)
    },
    
    getInitialState() {
        return { lastCheck: 0, checkCount: 0 };
    },
    
    analyze(lm, state, showHint, logError, calcAngle, plankTime) {
        const bodyAngle = calcAngle(lm[11], lm[23], lm[25]);
        const shoulderY = (lm[11].y + lm[12].y) / 2;
        const hipY = (lm[23].y + lm[24].y) / 2;
        
        let result = { counted: false, correct: false, status: 'Планка: ' + (plankTime || 0).toFixed(1) + 'с' };
        
        // Проверяем каждую секунду
        const currentCheck = Math.floor((plankTime || 0) * 10);
        if (currentCheck > state.lastCheck && currentCheck % this.thresholds.checkInterval === 0) {
            state.lastCheck = currentCheck;
            state.checkCount++;
            result.counted = true;
            
            if (bodyAngle < this.thresholds.bodyAngleMin) {
                showHint('Не провисайте! Напрягите пресс', this.svgIcons.bodyStraight);
                logError('Провисание корпуса на ' + (plankTime || 0).toFixed(1) + 'с');
                result.correct = false;
            } else if (bodyAngle > this.thresholds.bodyAngleMax) {
                showHint('Опустите бедра! Не поднимайте таз', this.svgIcons.hipsDown);
                logError('Бедра подняты слишком высоко на ' + (plankTime || 0).toFixed(1) + 'с');
                result.correct = false;
            } else if (Math.abs(shoulderY - hipY) > this.thresholds.hipShoulderDiff) {
                if (shoulderY < hipY) {
                    showHint('Поднимите бедра на уровень плеч!', this.svgIcons.hipsUp);
                } else {
                    showHint('Опустите бедра на уровень плеч!', this.svgIcons.hipsDown);
                }
                logError('Бедра не на уровне плеч на ' + (plankTime || 0).toFixed(1) + 'с');
                result.correct = false;
            } else {
                result.correct = true;
            }
        }
        
        return result;
    }
};
