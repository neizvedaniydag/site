export const mountain = {
    name: 'mountain',
    title: 'Альпинист (Mountain Climbers)',
    defaultReps: 30,
    
    instructions: [
        'Примите позицию планки на прямых руках',
        'Руки строго под плечами',
        'Тело образует прямую линию',
        'Быстро подтягивайте колено к груди',
        'Чередуйте ноги в динамичном темпе',
        'Держите корпус в планке, не поднимайте таз'
    ],
    
    svgIcons: {
        legLeft: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 20 L24 40 M32 20 L36 40" stroke="white" stroke-width="3"/><circle cx="24" cy="42" r="3"/><path d="M20 38 L24 42" stroke="white" stroke-width="2"/></svg>',
        legRight: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 20 L40 40 M32 20 L28 40" stroke="white" stroke-width="3"/><circle cx="40" cy="42" r="3"/><path d="M44 38 L40 42" stroke="white" stroke-width="2"/></svg>',
        plankPosition: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><rect x="20" y="28" width="24" height="4"/><circle cx="20" cy="30" r="3"/><circle cx="44" cy="30" r="3"/></svg>',
        check: '<svg width="48" height="48" viewBox="0 0 24 24" fill="white"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>'
    },
    
    thresholds: {
        kneeAngleBent: 90,      // Угол согнутого колена
        minTimeBetween: 500,    // Минимум 0.5 сек между сменами (антидребезг)
        bodyAngleMin: 150,      // Минимальный угол планки
        bodyAngleMax: 200       // Максимальный угол планки
    },
    
    getInitialState() {
        return { 
            position: 'neutral',
            lastChangeTime: 0
        };
    },
    
    analyze(lm, state, showHint, logError, calcAngle) {
        const now = performance.now();
        
        // Антидребезг - не засчитываем слишком быстрые смены
        if (now - state.lastChangeTime < this.thresholds.minTimeBetween) {
            return { counted: false, correct: false, status: 'Смена ' + (state.lastChangeTime > 0 ? '...' : '') };
        }
        
        const leftKnee = calcAngle(lm[23], lm[25], lm[27]);
        const rightKnee = calcAngle(lm[24], lm[26], lm[28]);
        const leftKneeY = lm[25].y;
        const rightKneeY = lm[26].y;
        const hipY = (lm[23].y + lm[24].y) / 2;
        const bodyAngle = calcAngle(lm[11], lm[23], lm[27]);
        
        // Проверяем что колено ДЕЙСТВИТЕЛЬНО подтянуто высоко к груди
        const leftBent = leftKnee < this.thresholds.kneeAngleBent && leftKneeY < hipY;
        const rightBent = rightKnee < this.thresholds.kneeAngleBent && rightKneeY < hipY;
        
        let result = { counted: false, correct: false, status: 'Чередуйте ноги' };
        
        if (leftBent && !rightBent && state.position !== 'left') {
            state.position = 'left';
            state.lastChangeTime = now;
            result.counted = true;
            
            // Проверяем планку
            if (bodyAngle < this.thresholds.bodyAngleMin || bodyAngle > this.thresholds.bodyAngleMax) {
                showHint('Держите планку! Не поднимайте таз', this.svgIcons.plankPosition);
                logError('Потеряна планка при смене на левую ногу');
                result.correct = false;
            } else {
                showHint('Левая! Теперь правая', this.svgIcons.legRight, 'rgba(16, 185, 129, 0.95)');
                result.correct = true;
            }
            result.status = 'Левая нога';
        } else if (rightBent && !leftBent && state.position !== 'right') {
            state.position = 'right';
            state.lastChangeTime = now;
            result.counted = true;
            
            // Проверяем планку
            if (bodyAngle < this.thresholds.bodyAngleMin || bodyAngle > this.thresholds.bodyAngleMax) {
                showHint('Держите планку! Не поднимайте таз', this.svgIcons.plankPosition);
                logError('Потеряна планка при смене на правую ногу');
                result.correct = false;
            } else {
                showHint('Правая! Теперь левая', this.svgIcons.legLeft, 'rgba(16, 185, 129, 0.95)');
                result.correct = true;
            }
            result.status = 'Правая нога';
        } else if (!leftBent && !rightBent) {
            result.status = 'Подтяните колено к груди';
        }
        
        return result;
    }
};
