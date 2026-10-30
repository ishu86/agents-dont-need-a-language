struct User { id: u32, name: String, email: Option<String> }

fn find(users: &[User], uid: u32) -> Option<&User> {
    users.iter().find(|u| u.id == uid)
}

fn total_age(ages: &[u32]) -> u32 {
    ages.iter().sum()
}

fn main() {
    let users = vec![User { id: 1, name: "a".into(), email: None }, User { id: 2, name: "b".into() }]; // 8
    let u = find(&users, "1");                                   // 1 wrong arg type
    println!("{}", u.name);                                      // 6 optional access
    println!("{}", users[0].nmae);                               // 2 typo
    let x: u32 = total_age(&[1, 2], 3);                          // 5 arg count
    println!("{}", undefined_var);                               // 4 undefined
    let y: String = total_age(&[1]);                             // 3 wrong type
    println!("{}", users[0].email.to_uppercase());               // 6b optional
}
