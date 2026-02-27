# Commit Examples

Representative commits from the analyzed corpus.

## 7dff99b35460 - Remove WARN_ALL_UNSEEDED_RANDOM kernel config option

This config option goes way back - it used to be an internal debug
option to random.c (at that point called DEBUG_RANDOM_BOOT), then was
renamed and exposed as a config option as CONFIG_WARN_UNSEEDED_RANDOM,
and then further renamed to the current CONFIG_WARN_ALL_UNSEEDED_RANDOM.

It was all done with the best of intentions: the more limited
rate-limited reports were reporting some cases, but if you wanted to see
all the gory details, you'd enable this "ALL" option.

However, it turns out - perhaps not surprisingly - that when people
don't care about and fix the first rate-limited cases, they most
certainly don't care about any others either, and so warning about all
of them isn't actually helping anything.

And the non-ratelimited reporting causes problems, where well-meaning
people enable debug options, but the excessive flood of messages that
nobody cares about will hide actual real information when things go
wrong.

I just got a kernel bug report (which had nothing to do with randomness)
where two thirds of the the truncated dmesg was just variations of

   random: get_random_u32 called from __get_random_u32_below+0x10/0x70 with crng_init=0

and in the process early boot messages had been lost (in addition to
making the messages that _hadn't_ been lost harder to read).

The proper way to find these things for the hypothetical developer that
cares - if such a person exists - is almost certainly with boot time
tracing.  That gives you the option to get call graphs etc too, which is
likely a requirement for fixing any problems anyway.

See Documentation/trace/boottime-trace.rst for that option.

And if we for some reason do want to re-introduce actual printing of
these things, it will need to have some uniqueness filtering rather than
this "just print it all" model.

Fixes: cc1e127bfa95 ("random: remove ratelimiting for in-kernel unseeded randomness")
Acked-by: Jason Donenfeld <Jason@zx2c4.com>
Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## 551d44200152 - default_gfp(): avoid using the "newfangled" __VA_OPT__ trick

The default_gfp() helper that I added is not wrong, but it turns out
that it causes unnecessary headaches for 'sparse' which doesn't support
the use of __VA_OPT__ (introduced in C++20 and C23, and supported by gcc
and clang for a long time).

We do already use __VA_OPT__ in some other cases in the kernel (drm/xe
and btrfs), but it has been fairly limited.  Now it triggers for pretty
much everything, and sparse ends up not working at all.

We can use the traditional gcc ',##__VA_ARGS__' syntax instead: it may
not be the "C standard" way and is slightly less natural in this
context, but it is the traditional model for this and avoids the sparse
problem.

Reported-and-tested-by: Ricardo Ribalda <ribalda@chromium.org>
Reported-and-tested-by: Richard Fitzgerald <rf@opensource.cirrus.com>
Reported-by: Ben Dooks <ben.dooks@codethink.co.uk>
Fixes: e19e1b480ac7 ("add default_gfp() helper macro and use it in the new *alloc_obj() helpers")
Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## 6de23f81a5e0 - Linux 7.0-rc1

## 32a92f8c8932 - Convert more 'alloc_obj' cases to default GFP_KERNEL arguments

This converts some of the visually simpler cases that have been split
over multiple lines.  I only did the ones that are easy to verify the
resulting diff by having just that final GFP_KERNEL argument on the next
line.

Somebody should probably do a proper coccinelle script for this, but for
me the trivial script actually resulted in an assertion failure in the
middle of the script.  I probably had made it a bit _too_ trivial.

So after fighting that far a while I decided to just do some of the
syntactically simpler cases with variations of the previous 'sed'
scripts.

The more syntactically complex multi-line cases would mostly really want
whitespace cleanup anyway.

Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## 323bbfcf1ef8 - Convert 'alloc_flex' family to use the new default GFP_KERNEL argument

This is the exact same thing as the 'alloc_obj()' version, only much
smaller because there are a lot fewer users of the *alloc_flex()
interface.

As with alloc_obj() version, this was done entirely with mindless brute
force, using the same script, except using 'flex' in the pattern rather
than 'objs*'.

Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## bf4afc53b77a - Convert 'alloc_obj' family to use the new default GFP_KERNEL argument

This was done entirely with mindless brute force, using

    git grep -l '\<k[vmz]*alloc_objs*(.*, GFP_KERNEL)' |
        xargs sed -i 's/\(alloc_objs*(.*\), GFP_KERNEL)/\1)/'

to convert the new alloc_obj() users that had a simple GFP_KERNEL
argument to just drop that argument.

Note that due to the extreme simplicity of the scripting, any slightly
more complex cases spread over multiple lines would not be triggered:
they definitely exist, but this covers the vast bulk of the cases, and
the resulting diff is also then easier to check automatically.

For the same reason the 'flex' versions will be done as a separate
conversion.

Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## e19e1b480ac7 - add default_gfp() helper macro and use it in the new *alloc_obj() helpers

Most simple allocations use GFP_KERNEL, and with the new allocation
helpers being introduced, let's just take advantage of that to simplify
that default case.

It's a numbers game:

    git grep 'alloc_obj(' |
	sed 's/.*\(GFP_[_A-Z]*\).*/\1/' |
	sort | uniq -c | sort -n | tail

shows that about 90% of all those new allocator instances just use that
standard GFP_KERNEL.

Those helpers are already macros, and we can easily just make it be the
default case when the gfp argument is missing.

And yes, we could do that for all the legacy interfaces too, but let's
keep it to just the new ones at least for now, since those all got
converted recently anyway, so this is not any "extra" noise outside of
that limited conversion.

And, in fact, I want to do this before doing the -rc1 release, exactly
so that we don't get extra merge conflicts.

Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## fa5c82f4d2bb - slab.h: disable completely broken overflow handling in flex allocations

Commit 69050f8d6d07 ("treewide: Replace kmalloc with kmalloc_obj for
non-scalar types") started using the new allocation helpers, and in the
process showed that they were completely non-working.

The overflow logic in overflows_flex_counter_type() is completely the
wrong way around, and that broke __alloc_flex() completely.  By chance,
the resulting code was then such a mess that clang generated
sufficiently garbage code that objtool warned about it all.  Which made
it somewhat quicker to narrow things down.

While fixing overflows_flex_counter_type() would presumably fix this
all, I'm excising the whole broken overflow logic from __alloc_flex(),
because we don't want that kind of code in basic allocation functions
anyway.

That (no longer) broken overflows_flex_counter_type() thing needs to be
inserted into the actual __set_flex_counter() logic in the unlikely case
that we ever want this at all.  And made conditional.

Fixes: 81cee9166a90 ("compiler_types: Introduce __flex_counter() and family")
Fixes: 69050f8d6d07 ("treewide: Replace kmalloc with kmalloc_obj for non-scalar types")
Cc: Kees Cook <kees@kernel.org>
Link: https://lore.kernel.org/all/CAHk-=whEd020BYzGTzYrENjD9Z5_82xx6h8HsQvH5xDSnv0=Hw@mail.gmail.com/
Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## 8429538c2c04 - tools/testing: keep legacy generated files around in .gitignore file

People keep removing generated files from .gitignore files even when the
files stay around.  Please don't do that: just because the file is no
longer being generated doesn't make it magically go away, and doesn't
make it suddenly be something that should now not be ignored any more.

Fixes: dd2c6ec24fca ("selftests/mm: remove virtual_address_range test")
Cc: Lorenzo Stoakes <lorenzo.stoakes@oracle.com>
Cc: SeongJae Park <sj@kernel.org>
Cc: Andrew Morton <akpm@linux-foundation.org>
Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## 1ca28333e464 - x86: keep legacy generated vdso files around in .gitignore file

Commit 93d73005bff4 ("x86/entry/vdso: Rename vdso_image_* to
vdso*_image") updated the vdso .gitignore file with the new filenames,
which is certainly not incorrect.

However, while adding new generated names is obviously the right thing
to do, you should *not* immediately remove the old filenames from the
.gitignore file when things move around or get renamed, because people
still have those old generated files in their build trees - and they
haven't suddenly become valid files to commit to the repository just
because they were moved or renamed.

While it's mostly just a slight visual nuisance for 'git status' that
can be fixed up with a clean build tree, it can become more serious than
that: see for example commit 04a3389b3535 ("Remove stale generated
'genheaders' file").

That commit removed up a stale generated file that had been carelessly
committed by a kernel developer because it wasn't properly ignored any
more and thus showed up as a new file in their tree.

Fixes: 93d73005bff4 ("x86/entry/vdso: Rename vdso_image_* to vdso*_image")
Cc: Peter Anvin <hpa@zytor.com>
Cc: Dave Hansen <dave.hansen@linux.intel.com>
Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## 35149653ee29 - smb client: Add generated file to gitignore file

The smb client code recently started generating the error mapping table
from a common header, but didn't tell git about it, so then git ends up
thinking maybe it should be committed.

Let's fix that.

Fixes: c527e13a7a66 ("cifs: Autogenerate SMB2 error mapping table")
Signed-off-by: Linus Torvalds <torvalds@linux-foundation.org>

## 05f7e89ab973 - Linux 6.19

## 18f7fcd5e69a - Linux 6.19-rc8

## 63804fed149a - Linux 6.19-rc7

## 24d479d26b25 - Linux 6.19-rc6

## 0f61b1860cc3 - Linux 6.19-rc5

## 9ace4753a520 - Linux 6.19-rc4

## f8f9c1f4d0c7 - Linux 6.19-rc3

## 9448598b22c5 - Linux 6.19-rc2

## 8f0b4cce4481 - Linux 6.19-rc1
