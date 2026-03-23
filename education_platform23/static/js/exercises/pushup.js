export const pushup = {
    name: 'pushup',
    title: 'Отжимания',
    defaultReps: 10,
    
    instructions: [
        'Упор лежа на прямых руках',
        'Тело образует прямую линию',
        'Опуститесь грудью почти до пола',
        'Локти согнуты на 90 градусов',
        'Выпрямите руки полностью'
    ],
    
    svgIcons: {
        bodyDown: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 10 L32 40 M26 34 L32 40 L38 34" stroke="white" stroke-width="3" fill="none"/><rect x="28" y="42" width="8" height="3"/></svg>',
        bodyUp: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 40 L32 10 M26 16 L32 10 L38 16" stroke="white" stroke-width="3" fill="none"/><rect x="28" y="8" width="8" height="3"/></svg>',
        bodyStraight: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><rect x="20" y="28" width="24" height="4"/><circle cx="20" cy="30" r="3"/><circle cx="44" cy="30" r="3"/></svg>',
        check: '<svg width="48" height="48" viewBox="0 0 24 24" fill="white"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>'
    },
    
    thresholds: {
        elbowAngleDown: 80,     // Угол локтя при опускании
        elbowAngleUp: 160,      // Угол локтя при подъеме
        elbowAngleGood: 50,     // Хороший угол опускания
        bodyAngleMin: 155,      // Минимальный угол тела
        bodyAngleMax: 195       // Максимальный угол тела
    },
    
    getInitialState() {
        return { position: 'up' };
    },
    
    analyze(lm, state, showHint, logError, calcAngle) {
        const elbow = (calcAngle(lm[11], lm[13], lm[15]) + calcAngle(lm[12], lm[14], lm[16])) / 2;
        const bodyAngle = calcAngle(lm[11], lm[23], lm[25]);
        
        let result = { counted: false, correct: false, status: 'Готов' };
        
        if (elbow < this.thresholds.elbowAngleDown && state.position === 'up') {
            state.position = 'down';
            result.counted = true;
            
            if (elbow > this.thresholds.elbowAngleGood) {
                showHint('Опускайтесь НИЖЕ! Грудь к полу', this.svgIcons.bodyDown);
                logError('Недостаточная глубина отжимания');
                result.correct = false;
            } else if (bodyAngle < this.thresholds.bodyAngleMin || bodyAngle > this.thresholds.bodyAngleMax) {
                showHint('Держите тело ПРЯМО!', this.svgIcons.bodyStraight);
                logError('Тело не прямое');
                result.correct = false;
            } else {
                showHint('Идеально! Выпрямите руки', this.svgIcons.bodyUp, 'rgba(16, 185, 129, 0.95)');
                result.correct = true;
            }
            result.status = 'Отжимание';
        } else if (elbow > this.thresholds.elbowAngleUp && state.position === 'down') {
            state.position = 'up';
            showHint('Готов к следующему', this.svgIcons.bodyDown);
            result.status = 'Готов';
        }
        
        return result;
    }
};
