// Moves items into any container beside a block. This is a child of Horizon's `machines` module, which
// keeps its hopper insert private.
use super::Game;
use horizon_client::items::ItemStack;
use horizon_core::geometry::Direction;

impl Game<'_> {
    pub(in crate::game) fn containers_max_stack(&self, stack: &ItemStack) -> u32 {
        self.containers().max_stack(stack)
    }

    /// `ResourceHandler.insert` through `face` of the container at `at`, as a hopper does it. What
    /// didn't fit, or the whole stack when there is no container. A machine's slot can hold more than
    /// a chest's, and Horizon's move drops whatever is past one stack, so this sends a stack at a time.
    pub(in crate::game) fn mek_insert_item(&mut self, at: [i32; 3], face: Direction, stack: ItemStack) -> Option<ItemStack> {
        let Some(target) = self.containers().view((at[0], at[1], at[2]), false) else {
            return Some(stack);
        };
        let most = self.containers().max_stack(&stack).max(1);
        let mut left = stack.count;
        while left > 0 {
            let count = left.min(most);
            let part = ItemStack { count, ..stack.clone() };
            let rest = self.add_item(None, &target, part, Some(face)).map_or(0, |rest| rest.count);
            left -= count - rest;
            if rest > 0 {
                break;
            }
        }
        (left > 0).then(|| ItemStack { count: left, ..stack })
    }
}
