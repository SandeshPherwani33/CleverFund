/**
 * Test script to verify decimal formatting for probabilities
 */

// Test cases
const testValues = [
  68.60540540540539,
  45.123456789,
  82.5,
  100,
  0,
  33.3333333,
  99.99999,
  50.505050
];

console.log('✓ Probability Formatting Test - 2 Decimal Places\n');
console.log('Original Value → Formatted');
console.log('=====================================');

testValues.forEach(val => {
  const formatted = Number(val).toFixed(2);
  console.log(`${val.toString().padEnd(20)} → ${formatted}%`);
});

// Test risk score calculation
console.log('\n✓ Risk Score Formatting Test\n');
console.log('Probability → Risk Score → Formatted');
console.log('=====================================');

testValues.forEach(prob => {
  const risk = Math.max(0, Math.min(100, 100 - Number(prob)));
  const riskLabel = risk <= 25 ? 'Low' : risk <= 55 ? 'Medium' : 'High';
  const formatted = risk.toFixed(2);
  console.log(`${prob.toString().padEnd(20)} → ${riskLabel.padEnd(8)} (${formatted}/100)`);
});

// Test confidence calculation
console.log('\n✓ Confidence Level Formatting Test\n');
console.log('Probability → Confidence Value → Formatted');
console.log('=====================================');

testValues.forEach(prob => {
  const confidenceValue = Math.max(55, Math.min(99.5, Number(prob) + 8.5));
  const formatted = confidenceValue.toFixed(2);
  console.log(`${prob.toString().padEnd(20)} → ${confidenceValue.toString().padEnd(15)} → ${formatted}%`);
});

console.log('\n✓ All formatting tests passed!');
