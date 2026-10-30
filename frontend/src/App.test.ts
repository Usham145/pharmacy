import { describe, expect, it } from 'vitest';
import { getExpirySnapshot } from './App';

describe('getExpirySnapshot', () => {
    it('marks expired stock as black', () => {
        const result = getExpirySnapshot('2020-01-01');

        expect(result.expiryBand).toBe('black');
        expect(result.expiryLabel).toBe('Expired');
    });

    it('marks disposed stock as black even when the date is in the future', () => {
        const result = getExpirySnapshot('2099-01-01', 'disposed');

        expect(result.expiryBand).toBe('black');
        expect(result.expiryLabel).toBe('Disposed');
    });

    it('marks stock expiring within ninety days as red', () => {
        const expiry = new Date();
        expiry.setDate(expiry.getDate() + 30);

        expect(getExpirySnapshot(expiry.toISOString().slice(0, 10)).expiryBand).toBe('red');
    });
});
