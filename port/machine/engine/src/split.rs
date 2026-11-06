//! `EmitUtils.sendToAcceptors` with `SplitInfo` and `Target`: how an amount divides among targets
//! that each have room for some of it. Everything is kept apart from the game, so a target is only
//! its room, the most it will take.

/// `SplitInfo`.
struct SplitInfo {
    amount_per_changed: bool,
    to_split_among: i64,
    amount_to_split: i64,
    amount_per_target: i64,
    remainder: i64,
}

impl SplitInfo {
    fn new(amount_to_split: i64, targets: i64) -> Self {
        Self {
            amount_per_changed: false,
            to_split_among: targets,
            amount_to_split,
            amount_per_target: amount_to_split / targets,
            remainder: amount_to_split % targets,
        }
    }

    fn send(&mut self, amount_needed: i64, decrement_targets: bool) {
        self.amount_to_split -= amount_needed;
        if !decrement_targets {
            let difference = amount_needed - self.amount_per_target;
            if difference > 0 {
                self.remainder -= difference;
            }
            return;
        }
        self.to_split_among -= 1;
        if amount_needed != self.amount_per_target && self.to_split_among != 0 {
            let last = self.amount_per_target;
            self.amount_per_target = self.amount_to_split / self.to_split_among;
            self.remainder = self.amount_to_split % self.to_split_among;
            if !self.amount_per_changed && self.amount_per_target != last {
                self.amount_per_changed = true;
            }
        }
    }

    fn remainder_amount(&self) -> i64 {
        if self.to_split_among != 0 && self.remainder > 0 {
            self.amount_per_target + 1
        } else {
            self.amount_per_target
        }
    }
}

/// What each target gets of `amount`, in the targets' order. `rooms` is what each will take.
pub fn split(amount: i64, rooms: &[i64]) -> Vec<i64> {
    let mut sent = vec![0; rooms.len()];
    if amount <= 0 || rooms.is_empty() {
        return sent;
    }
    if let [room] = rooms {
        sent[0] = amount.min(*room).max(0);
        return sent;
    }
    let mut info = SplitInfo::new(amount, rooms.len() as i64);
    let mut needed = send_possible(rooms, &mut info, &mut sent);
    while info.amount_per_changed {
        info.amount_per_changed = false;
        shift_needed(&mut needed, &mut info, &mut sent);
    }
    send_remaining(&mut needed, rooms, &mut info, &mut sent);
    sent
}

/// `Target.sendPossible`: targets wanting no more than a share get it. The rest are returned with
/// what they would take, in order.
fn send_possible(rooms: &[i64], info: &mut SplitInfo, sent: &mut [i64]) -> Vec<(usize, i64)> {
    let mut needed = Vec::new();
    for (index, room) in rooms.iter().enumerate() {
        let amount_needed = info.amount_to_split.min(*room).max(0);
        if amount_needed <= info.amount_per_target {
            info.send(amount_needed, true);
            sent[index] += amount_needed;
        } else {
            needed.push((index, amount_needed));
        }
    }
    needed
}

/// `Target.shiftNeeded`.
fn shift_needed(needed: &mut Vec<(usize, i64)>, info: &mut SplitInfo, sent: &mut [i64]) {
    if needed.is_empty() || info.amount_per_target == 0 {
        return;
    }
    let mut kept = Vec::with_capacity(needed.len());
    for (index, amount_needed) in needed.drain(..) {
        if amount_needed <= info.amount_per_target {
            info.send(amount_needed, true);
            sent[index] += amount_needed;
        } else {
            kept.push((index, amount_needed));
        }
    }
    *needed = kept;
}

/// `Target.sendRemainingSplit`.
fn send_remaining(
    needed: &mut Vec<(usize, i64)>,
    rooms: &[i64],
    info: &mut SplitInfo,
    sent: &mut [i64],
) {
    if needed.is_empty() || info.amount_to_split <= 0 {
        return;
    }
    if let [(index, _)] = needed.as_slice() {
        let index = *index;
        let accepted = info.amount_to_split.min(rooms[index] - sent[index]).max(0);
        info.send(accepted, false);
        sent[index] += accepted;
        return;
    }
    let mut kept = Vec::with_capacity(needed.len());
    for (position, (index, amount_needed)) in needed.iter().copied().enumerate() {
        let remainder_amount = info.remainder_amount();
        if remainder_amount == 0 {
            kept.extend_from_slice(&needed[position..]);
            *needed = kept;
            return;
        }
        if amount_needed <= remainder_amount {
            info.send(amount_needed, true);
            sent[index] += amount_needed;
        } else {
            info.send(remainder_amount, false);
            sent[index] += remainder_amount;
            kept.push((index, amount_needed));
        }
    }
    *needed = kept;
    for (index, _) in needed.iter() {
        if info.amount_to_split <= 0 {
            return;
        }
        let accepted = info
            .amount_to_split
            .min(rooms[*index] - sent[*index])
            .max(0);
        info.send(accepted, false);
        sent[*index] += accepted;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nothing_to_send_or_nobody_to_send_it_to() {
        assert_eq!(split(0, &[5, 5]), vec![0, 0]);
        assert_eq!(split(5, &[]), Vec::<i64>::new());
    }

    #[test]
    fn one_target_takes_what_fits() {
        assert_eq!(split(100, &[30]), vec![30]);
        assert_eq!(split(10, &[30]), vec![10]);
    }

    #[test]
    fn an_even_split() {
        assert_eq!(split(100, &[1000, 1000]), vec![50, 50]);
    }

    #[test]
    fn a_remainder_goes_one_at_a_time_from_the_first_target() {
        assert_eq!(split(7, &[1000, 1000]), vec![4, 3]);
        assert_eq!(split(11, &[1000, 1000, 1000]), vec![4, 4, 3]);
    }

    #[test]
    fn a_target_wanting_less_leaves_the_rest_to_the_others() {
        assert_eq!(
            split(4000, &[20, 1000000, 1000000, 20]),
            vec![20, 1980, 1980, 20]
        );
    }

    #[test]
    fn a_target_taking_nothing_still_counts_until_its_turn() {
        // `network_remainder` and the chain's last energy: 5 between two that each want 5.
        assert_eq!(split(5, &[5, 5]), vec![3, 2]);
        // With the output side of a cube among them, the same two still get 3 and 2.
        assert_eq!(split(5, &[0, 5, 5]), vec![0, 3, 2]);
    }

    #[test]
    fn nothing_is_lost_or_invented() {
        for amount in [1, 7, 99, 1000, 4000] {
            for rooms in [
                vec![3, 500, 8],
                vec![1, 1, 1, 1],
                vec![1000, 0, 2],
                vec![10, 20, 30, 40, 50],
            ] {
                let sent = split(amount, &rooms);
                let total: i64 = sent.iter().sum();
                assert_eq!(
                    total,
                    amount.min(rooms.iter().sum()),
                    "{amount} into {rooms:?}: {sent:?}"
                );
                assert!(
                    sent.iter().zip(&rooms).all(|(s, r)| s <= r),
                    "{sent:?} over {rooms:?}"
                );
            }
        }
    }
}
