use std::panic;
fn safe<F: FnOnce() -> String + panic::UnwindSafe>(f: F) -> String {
    panic::catch_unwind(f).unwrap_or_else(|_| "ERR:panic".into())
}
fn main() {
    panic::set_hook(Box::new(|_| {}));
    let v: Vec<i32> = vec![1, 2];
    let empty: Vec<i32> = vec![];
    let cases: Vec<(&str, Box<dyn FnOnce() -> String + panic::UnwindSafe>)> = vec![
        ("int_overflow 2**31*2", Box::new(|| { let x: i32 = std::hint::black_box(2i32.pow(30)); format!("{}", x.wrapping_mul(4)) })),
        ("big_int 2**64+1", Box::new(|| format!("{:?}", 2u64.checked_pow(64)))),
        ("div 7/2", Box::new(|| format!("{}", std::hint::black_box(7) / 2))),
        ("int_div -7//2", Box::new(|| format!("{}", std::hint::black_box(-7) / 2))),
        ("mod -7%3", Box::new(|| format!("{}", std::hint::black_box(-7) % 3))),
        ("round 2.5", Box::new(|| format!("{}", 2.5f64.round()))),
        ("round 0.5", Box::new(|| format!("{}", 0.5f64.round()))),
        ("len emoji 'a👍'", Box::new(|| format!("{}", "a👍".len()))),
        ("upper 'ß'", Box::new(|| "ß".to_uppercase())),
        ("sort [10,9,1]", Box::new(|| { let mut a = vec![10, 9, 1]; a.sort(); format!("{:?}", a) })),
        ("index out of range", Box::new(move || format!("{}", v[std::hint::black_box(5)]))),
        ("0.1+0.2", Box::new(|| format!("{}", 0.1f64 + 0.2))),
        ("float fmt 1.0", Box::new(|| format!("{}", 1.0f64))),
        ("1/0", Box::new(|| format!("{}", 1.0f64 / 0.0))),
        ("max empty", Box::new(move || format!("{:?}", empty.iter().max()))),
        ("str*3", Box::new(|| "ab".repeat(3))),
        ("'10' < '9'", Box::new(|| format!("{}", "10" < "9"))),
        ("int('08')", Box::new(|| format!("{:?}", "08".parse::<i32>()))),
    ];
    for (n, f) in cases { println!("{}\t{}", n, safe(f)); }
}
