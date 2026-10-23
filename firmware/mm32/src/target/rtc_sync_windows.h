/* State words 221..227 sit between reserved words and release state.
 * 221 next window tick; 222 window start; 223 state (0 seed,1 baseline,2 quiet,3 scan);
 * 224 last observation tick; 225 calibration edge seconds-of-day;
 * 226 anchor: 0 startup phase pending,1 valid,2 runtime rate baseline pending;
 * 227 projected calendar seconds.
 * Timer-driven civil time never stops because two RTC reads agree.
 */
#define sync_next seconds_log[221]
#define sync_start seconds_log[222]
#define sync_state seconds_log[223]
#define sync_sample_tick seconds_log[224]
#define sync_anchor_sod seconds_log[225]
#define sync_anchor_valid seconds_log[226]
#define sync_stamp seconds_log[227]

/* Free rtc_pace words: consecutive rejects, total rejects, reason, raw stamp.
 * Rejects never change the accepted time or frequency-calibration anchor. */
#define sync_bad_count rtc_pace[9]
#define sync_bad_total rtc_pace[10]
#define sync_bad_reason rtc_pace[11]
#define sync_bad_stamp rtc_pace[12]
static void rtc_window_bad(uint32_t code, uint32_t reason, uint32_t stamp, uint32_t tick)
{
    ++sync_bad_total;
    sync_bad_reason = reason;
    sync_bad_stamp = stamp;
    if (++sync_bad_count >= 3u)
    {
        fail(code);
        return;
    }
    if (reason == 1u)
    {
        /* A frozen clock produces no edge: count one expired window, not
         * three main-loop iterations at the same deadline. */
        sync_start = tick;
        sync_state = 1u;
    }
}

static void rtc_window_reset(uint32_t stamp, uint32_t tick)
{
    sync_stamp = stamp;
    /* A verified runtime calendar write is already a trusted clock seed.
     * Restart rate measurement, not civil time or its monotonic phase.
     * Only genuine startup may seed unconditionally from the RTC. */
    sync_state = rtc_clock_seeded ? 1u : 0u;
    sync_anchor_valid = rtc_clock_seeded ? 2u : 0u;
    sync_next = sync_start = sync_sample_tick = tick;
    sync_bad_count = 0u;
}

static void rtc_window_tick(uint32_t tick)
{
    if (!rtc_clock_seeded || !parallel_log[6])
        return;
    if (tick - rtc_edge_tick >= 128u)
    {
        rtc_edge_tick += 128u;
        ++rtc_pace[2];
        ++sync_stamp;
        uint32_t sod = sync_stamp % 86400u;
        parallel_log[5] = sod % 60u;
        parallel_log[15] = (sod / 60u) % 60u;
        parallel_log[16] = sod / 3600u;
        if (!parallel_log[5])
            rtc_boundary = 1u;
        rtc_pace[7] = sod;
        rtc_pace[8] = rtc_edge_tick;
    }
}

static void rtc_pace_poll(void)
{
    uint32_t tick = parallel_log[4];
    if (sync_state == 2u)
    {
        if ((int32_t)(tick - sync_next) < 0)
            return;
        sync_state = 1u;
        sync_start = tick;
    }
    if ((sync_state == 1u || sync_state == 3u) && tick - sync_start > 192u)
    {
        /* Every window has a 1.5-second limit, including a frozen RTC. */
        rtc_window_bad(rtc_failed_batches ? 8u : 9u, 1u, 0xffffffffu, tick);
        return;
    }
    if (sync_state && tick - rtc_poll_tick < 4u)
        return;
    uint32_t h = 0u, m = 0u, s = 0u;
    uint32_t ok = rtc_motion_read(&h, &m, &s);
    /* Schedule from completion: an ISR during bit-banged I2C must not
     * force another read immediately on the next main-loop poll. */
    tick = parallel_log[4];
    rtc_poll_tick = tick;
    if (parallel_log[2] == 6u)
        return;
    if (!ok)
    {
        ++rtc_pace[6];
        ++rtc_failed_batches;
        rtc_read_reason = rtc_motion_error();
        if (!sync_state)
        {
            sync_state = 1u;
            sync_start = tick;
        }
        rtc_window_bad(8u, 2u, 0xffffffffu, tick);
        return;
    }
    ++rtc_pace[5];
    uint32_t sod = h * 3600u + m * 60u + s, stamp = rtc_motion_stamp();
    if (stamp == 0xffffffffu)
    {
        rtc_window_bad(8u, 3u, stamp, tick);
        return;
    }
    if (!rtc_clock_seeded)
    {
        uint32_t mask;
        __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
        rtc_window_reset(stamp, tick);
        rtc_last = sod;
        rtc_clock_seeded = 1u;
        rtc_edge_tick = tick;
        sync_state = 3u;
        parallel_log[5] = s;
        parallel_log[15] = m;
        parallel_log[16] = h;
        __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
    }
    else
    {
        uint32_t projected = sync_stamp;
        if (stamp > projected + 2u || projected > stamp + 2u)
        {
            rtc_pace[14] = 1u;
            ++rtc_pace[15];
            rtc_window_bad(9u, 4u, stamp, tick);
            return;
        }
        /* A restarted runtime rate window has no prior RTC sample. The
         * verified civil-time check above is authoritative for its first
         * baseline; a permitted -1/-2s skew is not a 24-hour wrap. */
        uint32_t delta = (sync_state == 1u && sync_anchor_valid == 2u) ? 0u :
                         (sod + 86400u - rtc_last) % 86400u;
        uint32_t elapsed = tick - sync_sample_tick;
        /* Sparse reads may skip whole seconds. Validate against elapsed
         * timer time, permitting one-second read-boundary uncertainty. */
        if (delta && (delta > elapsed / 128u + 2u || delta + 2u < elapsed / 128u))
        {
            rtc_pace[14] = 1u;
            ++rtc_pace[15];
            rtc_window_bad(9u, 5u, stamp, tick);
            return;
        }
        if (sync_state == 1u)
        {
            /* The first sparse observation is not an observed boundary.
             * Establish its baseline and wait for a subsequent change. */
            rtc_last = sod;
            delta = 0u;
            sync_state = 3u;
        }
        if (delta)
        {
            uint32_t cycles = rtc_pace[0];
            if (sync_anchor_valid == 1u)
            {
                uint32_t seconds = (sod + 86400u - sync_anchor_sod) % 86400u;
                uint32_t span = cycles - rtc_window_cycles;
                if (seconds >= 7u && seconds <= 10u && pulse_diag[1] != 1u)
                {
                    /* Keep 1/1024-cycle precision, matching the existing
                     * fractional motor scheduler; do not truncate drift in. */
                    uint32_t measured = (span * 8u) / seconds;
                    uint32_t reload = measured / 1024u;
                    if (reload < 50000u || reload > 75000u)
                    {
                        rtc_window_bad(9u, 6u, stamp, tick);
                        return;
                    }
                    /* Smooth sampling jitter; never retime a motor pulse. */
                    uint32_t old = (rtc_pace[1] + 1u) * 1024u + release_state[1];
                    if (rtc_pace[4])
                        measured = (old * 7u + measured + 4u) / 8u;
                    reload = measured / 1024u;
                    uint32_t mask;
                    __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
                    rtc_pace[1] = reload - 1u;
                    REG32(0xe000e014u) = reload - 1u;
                    release_state[1] = measured % 1024u;
                    rtc_pace[4] = 1u;
                    __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
                }
            }
            else if (sync_anchor_valid == 0u)
            {
                /* Genuine startup only: establish the first real edge.
                 * A runtime write retains its verified monotonic phase. */
                uint32_t mask;
                __asm volatile("mrs %0, primask\n cpsid i" : "=r"(mask)::"memory");
                sync_stamp = stamp;
                rtc_edge_tick = tick;
                parallel_log[5] = s;
                parallel_log[15] = m;
                parallel_log[16] = h;
                rtc_boundary = (s == 0u);
                __asm volatile("msr primask, %0" ::"r"(mask) : "memory");
            }
            rtc_last = sod;
            rtc_window_cycles = cycles;
            sync_anchor_sod = sod;
            sync_anchor_valid = 1u;
            sync_state = 2u;
            sync_next = tick + 992u; /* Begin 7.75s after the observed edge. */
        }
    }
    sync_sample_tick = tick;
    rtc_good_read_tick = tick;
    /* A duplicate is not proof that a frozen RTC has recovered. Only an
     * accepted advancing edge clears a timed-out-window streak. */
    if (sync_state == 2u || sync_bad_reason != 1u)
        sync_bad_count = 0u;
    if (rtc_failed_batches)
        ++rtc_read_recoveries;
    rtc_failed_batches = 0u;
}
