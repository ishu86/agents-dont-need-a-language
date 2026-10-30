interface User { id: number; name: string; email?: string }

function find(users: User[], uid: number): User | undefined {
  return users.find(u => u.id === uid);
}

function totalAge(ages: number[]): number {
  return ages.reduce((a, b) => a + b, 0);
}

function main(): void {
  const users: User[] = [{ id: 1, name: "a" }, { id: 2 }];     // 8 missing field
  const u = find(users, "1");                                   // 1 wrong arg type
  console.log(u.name);                                          // 6 optional access
  console.log(users[0].nmae);                                   // 2 typo attribute
  const x: number = totalAge([1, 2], 3);                        // 5 wrong arg count
  console.log(undefinedVar);                                    // 4 undefined
  const y: string = totalAge([1]);                              // 3 wrong type
  console.log(users[0].email.toUpperCase());                    // 6b optional access
}
main();
